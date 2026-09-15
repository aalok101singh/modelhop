"""Tests for data models."""

from modelhop.core.models import (
    ComplexityLevel,
    HopScoreResult,
    ModelConfig,
    QueryAnalysis,
    QueryFeatures,
    QueryType,
    RoutingDecision,
    Tier,
)


class TestHopScoreResult:
    """Tests for HopScoreResult model."""

    def test_creation(self):
        result = HopScoreResult(
            score=85,
            total_queries=10,
            optimal_routes=8,
            rating="Great",
        )
        assert result.score == 85
        assert result.total_queries == 10
        assert result.optimal_routes == 8
        assert result.rating == "Great"

    def test_defaults(self):
        result = HopScoreResult(score=0, total_queries=0, optimal_routes=0, rating="N/A")
        assert result.score == 0
        assert result.total_queries == 0


class TestRoutingDecision:
    """Tests for RoutingDecision model."""

    def test_creation(self):
        model = ModelConfig(
            name="test-model",
            provider="groq",
            model="qwen/qwen3.8-27b",
            tier=Tier.FREE,
        )
        decision = RoutingDecision(
            model=model,
            tier=Tier.FREE,
            reason="Simple query",
        )
        assert decision.model.name == "test-model"
        assert decision.tier == Tier.FREE
        assert decision.reason == "Simple query"


class TestQueryFeatures:
    """Tests for QueryFeatures model."""

    def test_creation(self):
        features = QueryFeatures(
            length=25,
            has_question=True,
            technical_term_ratio=0.3,
            query_type=QueryType.GENERAL,
        )
        assert features.length == 25
        assert features.has_question is True
        assert features.technical_term_ratio == 0.3

    def test_defaults(self):
        features = QueryFeatures()
        assert features.length == 0
        assert features.has_code_block is False
        assert features.query_type == QueryType.GENERAL


class TestQueryAnalysis:
    """Tests for QueryAnalysis model."""

    def test_creation(self):
        analysis = QueryAnalysis(
            complexity=0.5,
            level=ComplexityLevel.MEDIUM,
            capabilities_needed=["reasoning"],
        )
        assert analysis.complexity == 0.5
        assert analysis.level == ComplexityLevel.MEDIUM
        assert "reasoning" in analysis.capabilities_needed


class TestModelConfig:
    """Tests for ModelConfig model."""

    def test_creation(self):
        config = ModelConfig(
            name="groq-model",
            provider="groq",
            model="qwen/qwen3.8-27b",
            tier=Tier.FREE,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
        )
        assert config.name == "groq-model"
        assert config.tier == Tier.FREE
        assert config.cost_per_1k_input == 0.0
