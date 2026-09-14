"""Tests for data models."""
import pytest
from modelhop.core.models import HopResult, RouteResult, QueryFeatures


class TestHopResult:
    """Tests for HopResult model."""

    def test_hop_result_creation(self):
        result = HopResult(
            query="test query",
            model="qwen/qwen3.8-27b",
            provider="groq",
            response="test response",
            cost=0.0,
            latency_ms=100.0,
            hop_score=0.85,
        )
        assert result.query == "test query"
        assert result.model == "qwen/qwen3.8-27b"
        assert result.provider == "groq"
        assert result.response == "test response"
        assert result.cost == 0.0
        assert result.latency_ms == 100.0
        assert result.hop_score == 0.85

    def test_hop_result_defaults(self):
        result = HopResult(
            query="test",
            model="model",
            provider="provider",
            response="response",
        )
        assert result.cost == 0.0
        assert result.latency_ms == 0.0
        assert result.hop_score == 0.0


class TestRouteResult:
    """Tests for RouteResult model."""

    def test_route_result_creation(self):
        result = RouteResult(
            model="qwen/qwen3.8-27b",
            provider="groq",
            tier="free",
            confidence=0.9,
            reasoning="Test query best suited for free tier",
        )
        assert result.model == "qwen/qwen3.8-27b"
        assert result.provider == "groq"
        assert result.tier == "free"
        assert result.confidence == 0.9


class TestQueryFeatures:
    """Tests for QueryFeatures model."""

    def test_query_features_creation(self):
        features = QueryFeatures(
            complexity=0.5,
            requires_code=False,
            requires_reasoning=True,
            language="en",
            domain="general",
            word_count=5,
            char_count=25,
        )
        assert features.complexity == 0.5
        assert features.requires_code is False
        assert features.requires_reasoning is True
