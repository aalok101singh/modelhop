"""Tests for ExperienceMemory round-trip."""

from modelhop.core.memory import ExperienceMemory
from modelhop.core.models import (
    ModelConfig,
    QueryAnalysis,
    QueryType,
    RoutingDecision,
    Tier,
)


def test_memory_write_read_similarity(tmp_path):
    # Set data dir to temp
    memory = ExperienceMemory(data_dir=str(tmp_path))
    extractor = memory.feature_extractor

    features1 = extractor.extract("Write a Python function")
    features2 = extractor.extract("Write a Python function to sort")

    model = ModelConfig(name="test-model", provider="x", model="x", tier=Tier.FREE)
    decision = RoutingDecision(model=model, tier=Tier.FREE, reason="test")
    analysis = QueryAnalysis(complexity=0.7, level="complex", capabilities_needed=["coding"])

    # Record first experience
    memory.record(
        query="Write a Python function",
        query_features=features1,
        analysis=analysis,
        decision=decision,
        response_quality=0.9,
        fallback_used=False,
        latency_ms=100,
    )

    # Record second experience
    memory.record(
        query="Write a Python function to sort",
        query_features=features2,
        analysis=analysis,
        decision=decision,
        response_quality=0.8,
        fallback_used=True,
        latency_ms=120,
    )

    # Similarity search should find both
    similar = memory.find_similar(features1, top_k=5, min_similarity=0.4)
    assert len(similar) == 2
    assert similar[0].query == "Write a Python function"

    # Persistence works
    memory2 = ExperienceMemory(data_dir=str(tmp_path))
    assert len(memory2.experiences) == 2


def test_memory_model_history(tmp_path):
    memory = ExperienceMemory(data_dir=str(tmp_path))
    features = memory.feature_extractor.extract("test query")
    model = ModelConfig(name="m1", provider="x", model="x", tier=Tier.FREE)
    decision = RoutingDecision(model=model, tier=Tier.FREE, reason="test")
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])

    memory.record(
        query="q1",
        query_features=features,
        analysis=analysis,
        decision=decision,
        response_quality=0.8,
        fallback_used=False,
        latency_ms=100,
    )
    history = memory.get_model_history("m1")
    assert len(history) == 1


def test_memory_get_quality_for_type(tmp_path):
    memory = ExperienceMemory(data_dir=str(tmp_path))
    features = memory.feature_extractor.extract("test query")
    model = ModelConfig(name="m1", provider="x", model="x", tier=Tier.FREE)
    decision = RoutingDecision(model=model, tier=Tier.FREE, reason="test")
    analysis = QueryAnalysis(complexity=0.5, level="medium", capabilities_needed=["general"])

    memory.record(
        query="q1",
        query_features=features,
        analysis=analysis,
        decision=decision,
        response_quality=0.9,
        fallback_used=False,
        latency_ms=100,
    )
    quality = memory.get_model_quality_for_type("m1", QueryType.GENERAL)
    assert quality == 0.9
