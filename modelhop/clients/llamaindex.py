"""LlamaIndex wrapper (v1.1 W2, [llamaindex] extra)."""

from __future__ import annotations


class ModelHopLlamaIndex:
    """Minimal LLM wrapper exposing ModelHop routing to LlamaIndex."""

    def __init__(self, mh=None, model: str = "auto"):
        if mh is None:
            try:
                from modelhop import ModelHop as _MH

                mh = _MH()
            except Exception as exc:
                raise ImportError("ModelHop SDK required") from exc
        self.mh = mh
        self.model = model
        self._last_result = None

    @property
    def metadata(self) -> dict:
        return {"model": self.model, "provider": "modelhop"}

    async def acomplete(self, prompt: str, **kwargs) -> str:
        if self.model != "auto":
            provider = self.mh.registry.get_provider(self.model)
            if provider is None:
                raise ValueError(f"Model {self.model} not found")
            resp = await provider.generate(prompt)
            return resp.content
        result = await self.mh.route(prompt)
        self._last_result = result
        return result.response

    def complete(self, prompt: str, **kwargs) -> str:
        import asyncio

        return asyncio.run(self.acomplete(prompt, **kwargs))
