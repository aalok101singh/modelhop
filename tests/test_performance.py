"""Tests for PerformanceTracker."""

from modelhop.core.memory import ExperienceMemory
from modelhop.core.models import QueryType
from modelhop.core.performance import PerformanceTracker


def test_performance_rebuild_from_memory(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    features = mem.feature_extractor.extract("test query")
    from modelhop.core.models import (
        ModelConfig,
        QueryAnalysis,
        RoutingDecision,
        Tier,
    )

    model = ModelConfig(name="m1", provider="x", model="x", tier=Tier.FREE)
    decision = RoutingDecision(model=model, tier=Tier.FREE, reason="test")
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])

    mem.record(
        query="q1",
        query_features=features,
        analysis=analysis,
        decision=decision,
        response_quality=0.9,
        fallback_used=False,
        latency_ms=100,
    )

    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))
    tracker.rebuild_from_memory()
    metrics = tracker.get_metrics("m1", QueryType.GENERAL)
    assert metrics is not None
    assert metrics.sample_count == 1
    assert metrics.avg_quality == 0.9


def test_record_outcome_updates_metrics(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))

    tracker.record_outcome(
        model_name="m1",
        query_type=QueryType.GENERAL,
        quality=0.8,
        latency_ms=100,
        fallback_used=False,
    )
    metrics = tracker.get_metrics("m1", QueryType.GENERAL)
    assert metrics.sample_count == 1
    assert metrics.avg_quality == 0.8
    assert metrics.fallback_rate == 0.0
    assert metrics.success_rate == 1.0


def test_fallback_rate_calculation(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))

    tracker.record_outcome("m1", QueryType.GENERAL, 0.9, 100, False)
    tracker.record_outcome("m1", QueryType.GENERAL, 0.7, 120, True)
    tracker.record_outcome("m1", QueryType.GENERAL, 0.8, 110, False)

    metrics = tracker.get_metrics("m1", QueryType.GENERAL)
    assert metrics.sample_count == 3
    # fallback_rate = 1/3 ≈ 0.333
    assert abs(metrics.fallback_rate - 0.333) < 0.01
    assert abs(metrics.success_rate - 0.667) < 0.01


def test_get_recommendation(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))

    tracker.record_outcome("model-good", QueryType.GENERAL, 0.9, 100, False)
    tracker.record_outcome("model-good", QueryType.GENERAL, 0.85, 110, False)
    tracker.record_outcome("model-bad", QueryType.GENERAL, 0.5, 200, True)
    tracker.record_outcome("model-bad", QueryType.GENERAL, 0.4, 210, True)

    recs = tracker.get_recommendation(QueryType.GENERAL, min_samples=2)
    assert len(recs) == 2
    assert recs[0][0] == "model-good"
    assert recs[1][0] == "model-bad"


def test_get_fallback_prone_models(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))

    for _ in range(5):
        tracker.record_outcome("prone-model", QueryType.GENERAL, 0.8, 100, True)
    for _ in range(5):
        tracker.record_outcome("stable-model", QueryType.GENERAL, 0.8, 100, False)

    prone = tracker.get_fallback_prone_models(threshold=0.3)
    assert "prone-model" in prone
    assert "stable-model" not in prone
