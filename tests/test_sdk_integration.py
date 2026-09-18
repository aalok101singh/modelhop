"""End-to-end SDK integration: real ModelHop.route() with injected fake providers.

Covers the main route() pipeline in modelhop/__init__.py (cache, policy, bandit,
generate, confidence, verifier gate, cost, ledger, memory, decomposed path).
Filesystem-isolated via tmp cwd; semantic embeddings stubbed to hash fallback.
"""

import pytest

from modelhop import ModelHop
from modelhop.cache.semantic import SemanticCache
from modelhop.core.models import ProviderResponse


class FakeProvider:
    def __init__(self):
        self.calls = 0
        self.last_prompt = None

    async def generate(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        self.calls += 1
        self.last_prompt = prompt
        return ProviderResponse(
            content="answer " * 100,
            model_used="fake",
            provider="fake",
            tokens_in=10,
            tokens_out=100,
            latency_ms=50,
        )


@pytest.fixture
def mh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Keep tests fast + offline: hash-vector fallback instead of fastembed.
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    inst = ModelHop()
    fake = FakeProvider()
    inst.registry._providers = {m.name: fake for m in inst.models}
    return inst, fake


async def test_route_end_to_end_zero_aux(mh):
    inst, fake = mh
    result = await inst.route("Hello world, this is a simple test query about passwords")
    assert result.model in {m.name for m in inst.models}
    assert result.response and len(result.response) > 50
    assert result.reasoning
    assert result.cost.aux_calls == 0
    assert fake.calls == 1
    assert result.degraded is False
    assert result.cached is False
    assert result.ledger_id


async def test_route_second_call_cached(mh):
    inst, fake = mh
    q = "What is the capital of France? Please answer briefly for this test."
    first = await inst.route(q)
    assert first.cached is False
    second = await inst.route(q)
    assert second.cached is True
    assert fake.calls == 1
    assert second.response == first.response


async def test_route_trust_refusal_fail_closed(mh):
    inst, _fake = mh
    with pytest.raises(RuntimeError, match="[Rr]efus"):
        await inst.route("hello test query", trust_required={"require_zdr": True})


async def test_route_with_session_budget(mh):
    inst, _fake = mh
    result = await inst.route("simple test query here", task_id="t1", budget=1.0)
    assert result.response
    assert len(inst.sessions.sessions) >= 1


async def test_route_decomposed_multi_part(mh):
    inst, fake = mh
    q = "Explain photosynthesis in detail and write a Python function to sort a list of numbers"
    result = await inst.route(q)
    assert fake.calls == 2
    assert "---" in result.response


async def test_route_no_provider_raises(mh):
    inst, _fake = mh
    inst.registry._providers = {}
    with pytest.raises(RuntimeError):
        await inst.route("hello test query")


async def test_explain_mentions_model(mh):
    inst, _fake = mh
    result = await inst.route("Hello world, this is a simple test query about passwords")
    text = inst.explain(result)
    assert result.model in text
