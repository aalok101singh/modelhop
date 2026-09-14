"""Shared fixtures for ModelHop tests."""
import pytest
from pathlib import Path


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
