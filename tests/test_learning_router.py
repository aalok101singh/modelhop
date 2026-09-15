"""Tests for LearningRouter."""

from modelhop.core.learning_router import LearningRouter
from modelhop.core.memory import ExperienceMemory
from modelhop.core.models import (
    ComplexityLevel,
    ModelConfig,
    QueryAnalysis,
    QueryFeatures,
    QueryType,
    Tier,
)
from modelhop.core.performance import PerformanceTracker


def test_no_memory_routes_complexity_based(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    perf = PerformanceTracker(mem, data_dir=str(tmp_path))

    models = [
        ModelConfig(name="free-a", provider="x", model="x", tier=Tier.FREE),
        ModelConfig(name="premium-a", provider="y", model="y", tier=Tier.PREMIUM),
    ]
    lr = LearningRouter(models, mem, perf)

    analysis = QueryAnalysis(
        complexity=0.2, level=ComplexityLevel.SIMPLE, capabilities_needed=["general"]
    )
    decision, _ = lr.route(analysis)
    assert decision.tier == Tier.FREE


def test_complex_query_routes_to_premium(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    perf = PerformanceTracker(mem, data_dir=str(tmp_path))

    models = [
        ModelConfig(
            name="free-a", provider="x", model="x", tier=Tier.FREE, capabilities=["general"]
        ),
        ModelConfig(
            name="premium-a",
            provider="y",
            model="y",
            tier=Tier.PREMIUM,
            capabilities=["coding", "reasoning"],
        ),
    ]
    lr = LearningRouter(models, mem, perf)

    analysis = QueryAnalysis(
        complexity=0.8, level=ComplexityLevel.COMPLEX, capabilities_needed=["coding"]
    )
    features = QueryFeatures(query_type=QueryType.IMPLEMENTATION, code_keyword_count=2)
    decision, _ = lr.route(analysis, features)
    assert decision.tier == Tier.PREMIUM


def test_neutral_complex_tries_free_first(tmp_path):
    mem = ExperienceMemory(data_dir=str(tmp_path))
    perf = PerformanceTracker(mem, data_dir=str(tmp_path))

    models = [
        ModelConfig(name="free-a", provider="x", model="x", tier=Tier.FREE),
        ModelConfig(name="premium-a", provider="y", model="y", tier=Tier.PREMIUM),
    ]
    lr = LearningRouter(models, mem, perf)

    analysis = QueryAnalysis(
        complexity=0.7, level=ComplexityLevel.COMPLEX, capabilities_needed=["general"]
    )
    decision, _ = lr.route(analysis)
    assert decision.tier == Tier.FREE
    assert "trying free first" in decision.reason.lower()
