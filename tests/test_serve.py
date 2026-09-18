"""HTTP layer tests: FastAPI OpenAI-compatible server (model=auto, SSE, auth).

Skipped when the [server] extra is not installed (CI dev-only job).
"""

from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from modelhop.core.models import (  # noqa: E402
    ConfidenceResult,
    CostAnalysis,
    ModelConfig,
    ProviderResponse,
    Tier,
    TrustProfile,
)
from modelhop.serve.app import create_app  # noqa: E402


def _result():
    from modelhop.core.models import RouteResult

    return RouteResult(
        response="stubbed answer",
        model="auto-a",
        tier="free",
        reasoning="stub",
        confidence=ConfidenceResult(score=0.9, is_confident=True, threshold=0.7),
        cost=CostAnalysis(
            actual_cost=0.0,
            would_have_cost=0.01,
            savings=0.01,
            savings_percentage=100.0,
            model_used="auto-a",
            tier="free",
        ),
        trust=TrustProfile(),
        ledger_id="abc123",
    )


def _stub_app(monkeypatch=None, api_key=None, explicit=None):
    models = [
        ModelConfig(
            name="auto-a",
            provider="x",
            model="auto-a",
            tier=Tier.FREE,
            capabilities=["general"],
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )
    ]

    async def fake_route(query):
        return _result()

    registry = SimpleNamespace(
        get_provider=lambda name: explicit,
        get_model=lambda name: models[0] if name == "auto-a" else None,
    )
    mh = SimpleNamespace(models=models, registry=registry, route=fake_route, secrets=None)
    if api_key is not None and monkeypatch is not None:
        monkeypatch.setenv("MODELHOP_API_KEY", api_key)
    return create_app(mh)


def test_list_models():
    client = TestClient(_stub_app())
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    assert body["data"][0]["id"] == "auto-a"


def test_chat_auto():
    client = TestClient(_stub_app())
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "auto-a"
    assert body["choices"][0]["message"]["content"] == "stubbed answer"


def test_chat_explicit_model():
    async def gen(query, **kw):
        return ProviderResponse(
            content="direct",
            model_used="auto-a",
            provider="x",
            tokens_in=1,
            tokens_out=1,
            latency_ms=1,
        )

    client = TestClient(_stub_app(explicit=SimpleNamespace(generate=gen)))
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto-a", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "direct"


def test_chat_unknown_model_404():
    client = TestClient(_stub_app())
    r = client.post(
        "/v1/chat/completions",
        json={"model": "nope", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 404


def test_chat_missing_messages_400():
    client = TestClient(_stub_app())
    r = client.post("/v1/chat/completions", json={"model": "auto", "messages": []})
    assert r.status_code == 400
    r = client.post("/v1/chat/completions", content=b"not json", headers={})
    assert r.status_code in (400, 422)


def test_chat_body_too_large_413():
    client = TestClient(_stub_app())
    big = "x" * (256 * 1024 + 10)
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": big}]},
    )
    assert r.status_code == 413


def test_chat_streaming_sse():
    client = TestClient(_stub_app())
    r = client.post(
        "/v1/chat/completions",
        json={"model": "auto", "stream": True, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "data: [DONE]" in r.text


def test_auth_required_and_accepted(monkeypatch):
    client = TestClient(_stub_app(monkeypatch, api_key="secret"))
    r = client.get("/v1/models")
    assert r.status_code == 401
    r = client.get("/v1/models", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    r = client.get("/v1/models", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
