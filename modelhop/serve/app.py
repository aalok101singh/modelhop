"""FastAPI OpenAI-compatible server (v1.1 W2).

- POST /v1/chat/completions (OpenAI schema, SSE streaming, model="auto")
- GET /v1/models
- Bearer auth from secrets; body size limits; rate limiting.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Optional

MAX_BODY_BYTES = 256 * 1024
RATE_LIMIT_PER_MIN = 120
MAX_RATE_LIMIT_CLIENTS = 10000

# Module-level import: FastAPI resolves handler annotations (Request, Header)
# via module globals. A function-local import leaves ForwardRef('Request')
# unresolvable (this file uses `from __future__ import annotations`), which
# makes every request fail validation with 422.
try:
    from fastapi import FastAPI, Header, HTTPException, Request  # type: ignore
    from fastapi.responses import StreamingResponse  # type: ignore

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - server extra not installed
    FastAPI = Header = HTTPException = Request = StreamingResponse = None  # type: ignore
    _FASTAPI_AVAILABLE = False


def create_app(mh=None, public_bind: bool = False):
    if not _FASTAPI_AVAILABLE:
        raise ImportError("Server extra required: pip install modelhop[server]")

    from modelhop.core.secrets import EnvSecretsProvider

    if mh is None:
        from modelhop import ModelHop

        mh = ModelHop()
    secrets = getattr(mh, "secrets", None) or EnvSecretsProvider()
    app = FastAPI(title="ModelHop", version="1.1.0")
    _hits: dict = defaultdict(list)

    def _server_key_configured() -> bool:
        try:
            return bool(secrets.get("MODELHOP_API_KEY") or secrets.get("OPENAI_API_KEY"))
        except Exception:
            return False

    # Fail-closed at startup: a public bind without a server key would expose
    # billable provider access to unauthenticated network clients.
    if public_bind and not _server_key_configured():
        raise RuntimeError(
            "Refusing public bind without MODELHOP_API_KEY/OPENAI_API_KEY. "
            "Bind 127.0.0.1 or set a server key."
        )

    def _check_auth(authorization: Optional[str] = Header(default=None)):
        try:
            expected = secrets.get("MODELHOP_API_KEY") or secrets.get("OPENAI_API_KEY")
        except Exception:
            # Fail closed: a broken secret backend must never open the server.
            raise HTTPException(status_code=503, detail="Secret backend unavailable")
        # Loopback-only single-user default: anon allowed only when no server
        # key is configured AND the server is not publicly bound.
        if not expected:
            if public_bind:
                raise HTTPException(
                    status_code=403, detail="Authentication required for public bind"
                )
            return True
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization[len("Bearer ") :].strip()
        if token != expected:
            raise HTTPException(status_code=401, detail="Invalid token")
        return True

    def _rate_limit(request: Request):
        key = request.client.host if request.client else "anon"
        now = time.time()
        window = [t for t in _hits.get(key, []) if now - t < 60]
        if not window:
            _hits.pop(key, None)
        else:
            _hits[key] = window
        # Bound memory: evict oldest clients when tracking too many.
        if len(_hits) > MAX_RATE_LIMIT_CLIENTS:
            oldest = next(iter(_hits))
            _hits.pop(oldest, None)
        if len(window) >= RATE_LIMIT_PER_MIN:
            raise HTTPException(status_code=429, detail="Rate limited")
        window.append(now)
        _hits[key] = window

    @app.get("/v1/models")
    async def list_models(request: Request, authorization: Optional[str] = Header(default=None)):
        _check_auth(authorization)
        _rate_limit(request)
        data = [
            {"id": m.name, "object": "model", "owned_by": m.provider, "tier": m.tier.value}
            for m in mh.models
        ]
        return {"object": "list", "data": data}

    @app.post("/v1/chat/completions")
    async def chat_completions(
        request: Request, authorization: Optional[str] = Header(default=None)
    ):
        _check_auth(authorization)
        _rate_limit(request)
        # Pre-check Content-Length before buffering (covers non-chunked bodies).
        try:
            content_length = request.headers.get("content-length")
            if content_length is not None and int(content_length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Request body too large")
        except HTTPException:
            raise
        except Exception:
            pass
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body too large")
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Invalid JSON")
        messages = payload.get("messages", [])
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages required")
        # Concatenate user messages as the query.
        query = " ".join(
            str(m.get("content", ""))
            for m in messages
            if isinstance(m, dict) and m.get("role") in ("user", "system")
        ).strip() or str(messages[-1].get("content", ""))
        model_req = str(payload.get("model", "auto"))
        stream = bool(payload.get("stream", False))

        if model_req != "auto":
            # Explicit model, still gated by the server's trust + health
            # policy (never a raw passthrough).
            provider = mh.registry.get_provider(model_req)
            cfg = mh.registry.get_model(model_req)
            if provider is None or cfg is None:
                raise HTTPException(status_code=404, detail=f"Model {model_req} not found")
            try:
                from modelhop.core.trust import filter_by_trust

                eligible, _ = filter_by_trust([cfg], getattr(mh, "trust_policy", None) or {}, {})
                if not eligible:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Model {model_req} excluded by server trust policy",
                    )
            except HTTPException:
                raise
            except Exception:
                pass
            try:
                health = getattr(mh, "health", None)
                if health is not None and hasattr(health, "allow") and not health.allow(cfg.name):
                    raise HTTPException(
                        status_code=503, detail=f"Model {model_req} temporarily unhealthy"
                    )
            except HTTPException:
                raise
            except Exception:
                pass
            try:
                resp = await provider.generate(query)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc))
            content = resp.content
            model_name = cfg.name
        else:
            try:
                result = await mh.route(query)
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=403 if "refused" in str(exc).lower() else 502, detail=str(exc)
                )
            content = result.response
            model_name = result.model

        if not stream:
            return {
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

        async def _gen():
            chunk_id = f"chatcmpl-{int(time.time()*1000)}"
            # SSE streaming in small chunks.
            for i in range(0, len(content), 200):
                piece = content[i : i + 200]
                yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_name, 'choices': [{'index': 0, 'delta': {'content': piece}, 'finish_reason': None}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_gen(), media_type="text/event-stream")

    return app


try:
    app = create_app()
except Exception:
    app = None  # Import-time safety when deps/config missing; create_app() works at runtime.
