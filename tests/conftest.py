"""Shared fixtures for ModelHop tests."""

from datetime import datetime

import pytest

from modelhop.core.models import (
    ComplexityLevel,
    ConfidenceResult,
    CostAnalysis,
    ModelConfig,
    ProviderResponse,
    QueryAnalysis,
    RoutingDecision,
    Tier,
    TraceEntry,
)


@pytest.fixture
def sample_queries():
    """Sample queries for testing."""
    return [
        "How do I reset my password?",
        "What is machine learning?",
        "Write a Python function to sort a list",
        "Explain quantum computing in simple terms",
        "Help me debug this code",
    ]


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "models": [
            {
                "name": "groq-qwen3-8-27b",
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",
                "tier": "free",
                "capabilities": ["faq", "general", "classification", "reasoning"],
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "api_key_env": "GROQ_API_KEY",
            },
            {
                "name": "gemini-3.6-flash",
                "provider": "gemini",
                "model": "gemini-3.6-flash",
                "tier": "free",
                "capabilities": ["faq", "general", "reasoning"],
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "api_key_env": "GEMINI_API_KEY",
            },
        ]
    }


@pytest.fixture
def make_model():
    def _make(name, tier, caps=(), cost_in=0.0, cost_out=0.0):
        return ModelConfig(
            name=name,
            provider="x",
            model=name,
            tier=tier,
            capabilities=list(caps),
            cost_per_1k_input=cost_in,
            cost_per_1k_output=cost_out,
        )

    return _make


@pytest.fixture
def sample_models(make_model):
    """Three routable models: two free, one premium."""
    return [
        make_model(
            "free-a",
            Tier.FREE,
            ["faq", "general", "reasoning", "coding"],
        ),
        make_model(
            "free-b",
            Tier.FREE,
            ["faq", "general"],
        ),
        make_model(
            "premium-a",
            Tier.PREMIUM,
            ["reasoning", "coding", "creative", "analysis"],
            cost_in=0.03,
            cost_out=0.06,
        ),
    ]


@pytest.fixture
def make_analysis():
    def _make(complexity=0.5, caps=("general",)):
        return QueryAnalysis(
            complexity=complexity,
            level=(
                ComplexityLevel.SIMPLE
                if complexity <= 0.3
                else ComplexityLevel.MEDIUM if complexity <= 0.6 else ComplexityLevel.COMPLEX
            ),
            capabilities_needed=list(caps),
        )

    return _make


@pytest.fixture
def make_trace(sample_models):
    def _make(score, query="test query", threshold=0.7):
        model = sample_models[0]
        return TraceEntry(
            query_id="qid-1",
            query=query,
            timestamp=datetime.now(),
            analysis=QueryAnalysis(
                complexity=0.5, level=ComplexityLevel.MEDIUM, capabilities_needed=["general"]
            ),
            decision=RoutingDecision(model=model, tier=model.tier, reason="test"),
            response=ProviderResponse(
                content="answer", model_used=model.name, provider="x", tokens_in=100, tokens_out=50
            ),
            confidence=ConfidenceResult(
                score=score, is_confident=score >= threshold, threshold=threshold
            ),
            cost=CostAnalysis(
                actual_cost=0.0,
                would_have_cost=0.01,
                savings=0.01,
                savings_percentage=100.0,
                model_used=model.name,
                tier=model.tier.value,
            ),
        )

    return _make
