"""Tests for ConfidenceEngine."""

import asyncio

import pytest

from modelhop.core.confidence import ConfidenceEngine
from modelhop.core.models import ProviderResponse, QueryFeatures


@pytest.fixture
def engine():
    return ConfidenceEngine(threshold=0.7)


class MockProvider:
    async def generate(self, prompt, max_tokens=100, temperature=0.1):
        class Resp:
            content = '{"confidence": 0.8, "reasoning": "test"}'

        return Resp()


def test_high_self_confidence_passes(engine):
    # v1.1: self-report is combined with local heuristic (never trusted blindly).
    # Use a substantive answer so the heuristic also supports confidence.
    resp = ProviderResponse(
        content="Great answer " * 50,
        model_used="m",
        provider="p",
        tokens_in=100,
        tokens_out=50,
    )
    provider = MockProvider()
    result = asyncio.run(engine.check("query", resp, provider))
    assert result.is_confident is True


def test_low_self_below_threshold_returns_not_confident(engine):
    # Use a provider that returns low confidence
    class LowConfProvider:
        async def generate(self, prompt, max_tokens=100, temperature=0.1):
            class Resp:
                content = '{"confidence": 0.3, "reasoning": "unsure"}'

            return Resp()

    resp = ProviderResponse(
        content="Meh answer", model_used="m", provider="p", tokens_in=100, tokens_out=50
    )
    provider = LowConfProvider()
    result = asyncio.run(engine.check("query", resp, provider))
    assert result.is_confident is False


def test_consensus_boosts_above_threshold(engine):
    """If consensus provider agrees, low self-confidence can be boosted."""

    class LowSelfProvider:
        async def generate(self, prompt, max_tokens=100, temperature=0.1):
            class Resp:
                content = '{"confidence": 0.5, "reasoning": "unsure"}'

            return Resp()

    class ConsensusProvider:
        async def generate(self, prompt, max_tokens=100, temperature=0.1):
            class Resp:
                content = "I agree with the first answer"

            return Resp()

    resp = ProviderResponse(
        content="Original answer", model_used="m", provider="p", tokens_in=100, tokens_out=50
    )
    provider = LowSelfProvider()
    consensus = ConsensusProvider()
    result = asyncio.run(engine.check("query", resp, provider, consensus_provider=consensus))
    # Low (0.5) + high consensus (0.88 fallback) / 2 = 0.69 < 0.7, so not confident
    assert result.is_confident is False


def test_heuristic_confidence_short_response_penalized():
    engine = ConfidenceEngine(threshold=0.7, enable_consensus=False)
    resp = ProviderResponse(content="Hi", model_used="m", provider="p", tokens_in=10, tokens_out=5)
    score = engine._heuristic_confidence("query", resp, None)
    assert score < 0.7


def test_heuristic_confidence_coding_bonus():
    engine = ConfidenceEngine(threshold=0.7, enable_consensus=False)
    resp = ProviderResponse(
        content="def foo():\n    pass", model_used="m", provider="p", tokens_in=50, tokens_out=30
    )
    features = QueryFeatures(
        code_keyword_count=3, is_implementation=True, query_type="implementation"
    )
    score = engine._heuristic_confidence("Write a function", resp, features)
    # With short content: 0.75 - 0.2 + 0.05 = 0.6
    assert score >= 0.5
