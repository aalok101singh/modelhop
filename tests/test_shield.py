import pytest

"""Tests for Shield quality monitoring."""
from datetime import datetime

from modelhop.core.models import (
    ConfidenceResult,
    CostAnalysis,
    ModelConfig,
    ProviderResponse,
    QueryAnalysis,
    RoutingDecision,
    Tier,
    TraceEntry,
)
from modelhop.shield.shield import Shield


@pytest.fixture
def shield(tmp_path):
    return Shield(quality_threshold=0.8, data_dir=str(tmp_path))


@pytest.fixture
def make_trace():
    def _make(score):
        model = ModelConfig(name="m", provider="p", model="m", tier=Tier.FREE)
        return TraceEntry(
            query_id="q1",
            query="test",
            timestamp=datetime.now(),
            analysis=QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"]),
            decision=RoutingDecision(model=model, tier=Tier.FREE, reason="test"),
            response=ProviderResponse(
                content="ans", model_used="m", provider="p", tokens_in=100, tokens_out=50
            ),
            confidence=ConfidenceResult(score=score, is_confident=score >= 0.8, threshold=0.8),
            cost=CostAnalysis(
                actual_cost=0.0,
                would_have_cost=0.01,
                savings=0.01,
                savings_percentage=100.0,
                model_used="m",
                tier="free",
            ),
        )

    return _make


def test_high_confidence_returns_true(shield, make_trace):
    trace = make_trace(0.9)
    assert shield.check_quality(trace) is True


def test_low_confidence_adds_alert(shield, make_trace):
    trace = make_trace(0.5)
    assert shield.check_quality(trace) is False
    assert len(shield.alerts) == 1
    assert "Low confidence" in shield.alerts[0]


def test_degradation_detected(shield, make_trace):
    # 5 good then 5 bad
    for _ in range(5):
        shield.check_quality(make_trace(0.9))
    for _ in range(5):
        shield.check_quality(make_trace(0.5))
    assert shield._detect_degradation() is True
    assert len(shield.alerts) >= 2  # low + degradation


def test_get_recommendations_low_quality(shield, make_trace):
    shield.check_quality(make_trace(0.5))
    recs = shield.get_recommendations()
    assert len(recs) > 0
    assert any("lowering confidence threshold" in r.lower() for r in recs)
