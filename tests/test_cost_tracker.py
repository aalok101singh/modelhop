import pytest

"""Tests for CostTracker savings math."""
from modelhop.core.models import ModelConfig, ProviderResponse, Tier
from modelhop.tracking.cost_tracker import CostTracker, estimate_cost


@pytest.fixture
def free_model():
    return ModelConfig(
        name="free-model",
        provider="groq",
        model="qwen/qwen3.8-27b",
        tier=Tier.FREE,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    )


@pytest.fixture
def premium_model():
    return ModelConfig(
        name="premium-model",
        provider="openai",
        model="gpt-4",
        tier=Tier.PREMIUM,
        cost_per_1k_input=0.03,
        cost_per_1k_output=0.06,
    )


def test_free_model_saves_100_percent(free_model):
    tracker = CostTracker()
    resp = ProviderResponse(
        content="answer",
        model_used=free_model.name,
        provider="groq",
        tokens_in=1000,
        tokens_out=500,
    )
    analysis = tracker.calculate(resp, free_model)
    assert analysis.actual_cost == 0.0
    assert analysis.savings_percentage == 100.0
    assert analysis.tier == "free"


def test_premium_model_saves_less(premium_model):
    tracker = CostTracker()
    resp = ProviderResponse(
        content="answer",
        model_used=premium_model.name,
        provider="openai",
        tokens_in=1000,
        tokens_out=500,
    )
    analysis = tracker.calculate(resp, premium_model)
    actual = (1000 / 1000) * 0.03 + (500 / 1000) * 0.06
    would = (1000 / 1000) * 0.03 + (500 / 1000) * 0.06
    assert analysis.actual_cost == actual
    assert analysis.would_have_cost == would
    assert analysis.savings_percentage == 0.0
    assert analysis.tier == "premium"


def test_get_summary_zero_history(tmp_path):
    tracker = CostTracker(log_path=str(tmp_path / "cost_log.json"))
    summary = tracker.get_summary()
    assert summary["total_cost"] == 0.0
    assert summary["total_savings"] == 0.0
    assert summary["savings_percentage"] == 0.0
    assert summary["query_count"] == 0


def test_savings_percentage_calculation(tmp_path):
    tracker = CostTracker(log_path=str(tmp_path / "cost_log.json"))
    free = ModelConfig(name="f", provider="x", model="x", tier=Tier.FREE)
    premium = ModelConfig(name="p", provider="y", model="y", tier=Tier.PREMIUM)
    resp_f = ProviderResponse(
        content="a", model_used="f", provider="x", tokens_in=1000, tokens_out=1000
    )
    resp_p = ProviderResponse(
        content="b", model_used="p", provider="y", tokens_in=1000, tokens_out=1000
    )
    tracker.calculate(resp_f, free)
    tracker.calculate(resp_p, premium)
    summary = tracker.get_summary()
    assert summary["query_count"] == 2


def test_estimate_cost_helper(free_model):
    resp = ProviderResponse(
        content="answer",
        model_used=free_model.name,
        provider="groq",
        tokens_in=1000,
        tokens_out=500,
    )
    analysis = estimate_cost(resp, free_model)
    assert analysis.actual_cost == 0.0
    assert analysis.would_have_cost > 0.0
    assert analysis.savings_percentage == 100.0
