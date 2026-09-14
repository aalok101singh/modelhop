"""Tests for QueryAnalyzer."""
import pytest
from modelhop.core.analyzer import QueryAnalyzer


class TestQueryAnalyzer:
    """Tests for QueryAnalyzer feature extraction."""

    def test_simple_query(self):
        analyzer = QueryAnalyzer()
        features = analyzer.analyze("Hello, how are you?")
        assert features.word_count == 4
        assert features.char_count == 19
        assert features.complexity < 0.5

    def test_complex_query(self):
        analyzer = QueryAnalyzer()
        features = analyzer.analyze(
            "Write a Python function that implements quicksort algorithm "
            "with proper error handling and type hints"
        )
        assert features.requires_code is True
        assert features.complexity > 0.5

    def test_reasoning_query(self):
        analyzer = QueryAnalyzer()
        features = analyzer.analyze("Explain the theory of relativity in simple terms")
        assert features.requires_reasoning is True

    def test_language_detection(self):
        analyzer = QueryAnalyzer()
        features = analyzer.analyze("This is an English sentence")
        assert features.language == "en"

    def test_empty_query(self):
        analyzer = QueryAnalyzer()
        features = analyzer.analyze("")
        assert features.word_count == 0
        assert features.char_count == 0
