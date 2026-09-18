"""clients/: MCP tool hook + LlamaIndex wrapper."""

from types import SimpleNamespace

import pytest

from modelhop.clients.llamaindex import ModelHopLlamaIndex
from modelhop.clients.mcp import mcp_tool_hook


class _FakeMH:
    def __init__(self):
        self.calls = []

    async def route(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return SimpleNamespace(response="routed answer", model="fake-a", degraded=False)


async def test_mcp_tool_hook_routes_with_tool_context():
    mh = _FakeMH()
    out = await mcp_tool_hook(
        "summarize this",
        "search",
        {"q": "x", "limit": 3},
        mh=mh,
        trust_required={"require_zdr": True},
    )
    assert out == {"response": "routed answer", "model": "fake-a", "degraded": False}
    query, kwargs = mh.calls[0]
    assert query == "summarize this"
    assert kwargs["context"] == {"tool": "search", "tool_args_keys": ["limit", "q"]}
    assert kwargs["trust_required"] == {"require_zdr": True}


async def test_mcp_tool_hook_defaults(monkeypatch):
    mh = _FakeMH()
    monkeypatch.setattr("modelhop.ModelHop", lambda *a, **k: mh)
    out = await mcp_tool_hook("hi", "lookup")
    assert out["response"] == "routed answer"
    _, kwargs = mh.calls[0]
    assert kwargs["context"] == {"tool": "lookup", "tool_args_keys": []}
    assert kwargs["trust_required"] == {}


def test_llamaindex_metadata_and_auto_route():
    mh = _FakeMH()
    llm = ModelHopLlamaIndex(mh=mh)
    assert llm.metadata == {"model": "auto", "provider": "modelhop"}
    assert llm.complete("hello?") == "routed answer"
    assert llm._last_result.model == "fake-a"


async def test_llamaindex_named_model_passthrough():
    async def _generate(prompt):
        return SimpleNamespace(content=f"direct:{prompt}")

    provider = SimpleNamespace(generate=_generate)
    mh = SimpleNamespace(registry=SimpleNamespace(get_provider=lambda name: provider))
    llm = ModelHopLlamaIndex(mh=mh, model="fake-a")
    assert await llm.acomplete("ping") == "direct:ping"


async def test_llamaindex_named_model_missing():
    mh = SimpleNamespace(registry=SimpleNamespace(get_provider=lambda name: None))
    llm = ModelHopLlamaIndex(mh=mh, model="ghost")
    with pytest.raises(ValueError, match="ghost"):
        await llm.acomplete("ping")


def test_llamaindex_requires_sdk(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("no sdk")

    monkeypatch.setattr("modelhop.ModelHop", _boom)
    with pytest.raises(ImportError, match="ModelHop SDK required"):
        ModelHopLlamaIndex()
