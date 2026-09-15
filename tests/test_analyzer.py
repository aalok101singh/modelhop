"""Tests for QueryAnalyzer."""

from modelhop.core.analyzer import QueryAnalyzer
from modelhop.core.models import ComplexityLevel


class TestQueryAnalyzer:
    """Tests for QueryAnalyzer heuristic analysis."""

    def test_simple_query(self):
        analyzer = QueryAnalyzer(providers=[])
        result = analyzer._heuristic_analysis("Hello, how are you?")
        assert result.complexity < 0.6
        assert result.level == ComplexityLevel.MEDIUM
        assert "general" in result.capabilities_needed

    def test_coding_query(self):
        analyzer = QueryAnalyzer(providers=[])
        result = analyzer._heuristic_analysis(
            "Write a Python function to sort a list using quicksort algorithm"
        )
        assert result.complexity >= 0.7
        assert result.level == ComplexityLevel.COMPLEX
        assert "coding" in result.capabilities_needed

    def test_algorithm_query(self):
        analyzer = QueryAnalyzer(providers=[])
        result = analyzer._heuristic_analysis(
            "Implement a binary search with O(log n) time complexity"
        )
        assert result.complexity >= 0.7
        assert result.level == ComplexityLevel.COMPLEX

    def test_long_query(self):
        analyzer = QueryAnalyzer(providers=[])
        long_query = "Explain " + " ".join(["this"] * 100)
        result = analyzer._heuristic_analysis(long_query)
        assert result.complexity >= 0.6

    def test_empty_query(self):
        analyzer = QueryAnalyzer(providers=[])
        result = analyzer._heuristic_analysis("")
        assert result.complexity == 0.5
        assert result.level == ComplexityLevel.MEDIUM
