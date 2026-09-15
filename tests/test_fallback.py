"""Tests for CascadeFallback."""

import asyncio

import pytest

from modelhop.core.fallback import CascadeFallback
from modelhop.core.models import (
    ConfidenceResult,
    ModelConfig,
    QueryAnalysis,
    Tier,
)


@pytest.fixture
def models(make_model):
    return [
        make_model("free-a", Tier.FREE, ["general"]),
        make_model("mid-a", Tier.MID, ["general", "reasoning"]),
        make_model("premium-a", Tier.PREMIUM, ["reasoning", "coding"], cost_in=0.03, cost_out=0.06),
    ]


@pytest.fixture
def fallback(models):
    return CascadeFallback(models, max_retries=3)


def test_next_tier_from_free_returns_mid(fallback):
    next_tier = fallback.get_next_tier(Tier.FREE)
    assert next_tier == Tier.MID


def test_next_tier_from_mid_returns_premium(fallback):
    next_tier = fallback.get_next_tier(Tier.MID)
    assert next_tier == Tier.PREMIUM


def test_next_tier_from_premium_returns_none(fallback):
    next_tier = fallback.get_next_tier(Tier.PREMIUM)
    assert next_tier is None


def test_handle_failure_returns_next_tier_model(fallback):
    failed = fallback.models[0]  # free-a
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])
    result = asyncio.run(fallback.handle_failure("query", analysis, failed))
    assert result is not None
    assert result.tier == Tier.MID


def test_handle_failure_at_premium_returns_none(fallback):
    failed = fallback.models[2]  # premium-a
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])
    result = asyncio.run(fallback.handle_failure("query", analysis, failed))
    assert result is None


def test_handle_low_confidence_delegates_to_handle_failure(fallback):
    current = fallback.models[0]  # free-a
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])
    confidence = ConfidenceResult(score=0.4, is_confident=False, threshold=0.7)
    result = asyncio.run(fallback.handle_low_confidence("query", analysis, current, confidence))
    assert result is not None
    assert result.tier == Tier.MID


def test_fallback_skips_empty_tier():
    """Free → Premium escalation works when MID tier is empty."""
    models = [
        ModelConfig(
            name="free-a", provider="x", model="x", tier=Tier.FREE, capabilities=["general"]
        ),
        ModelConfig(
            name="premium-a", provider="y", model="y", tier=Tier.PREMIUM, capabilities=["reasoning"]
        ),
    ]
    fb = CascadeFallback(models, max_retries=3)
    next_tier = fb.get_next_tier(Tier.FREE)
    assert next_tier == Tier.PREMIUM
    models_for_tier = fb.get_models_for_tier(Tier.MID)
    assert models_for_tier == []
