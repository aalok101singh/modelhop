import pytest

"""Tests for FeatureExtractor."""
from modelhop.core.features import FeatureExtractor


@pytest.fixture
def extractor():
    return FeatureExtractor()


def test_extract_code_query(extractor):
    query = "Write a Python function to sort an array using quicksort algorithm"
    features = extractor.extract(query)
    assert features.code_keyword_count >= 2
    assert features.algorithm_term_count >= 1
    assert features.query_type.value == "implementation"


def test_extract_debug_query(extractor):
    query = "Fix the bug in my code: null pointer exception when calling function"
    features = extractor.extract(query)
    assert features.is_debugging
    assert features.query_type.value == "debugging"


def test_extract_creative_query(extractor):
    query = "Write a creative story about a frog who learns to fly"
    features = extractor.extract(query)
    assert features.is_creative
    assert features.query_type.value == "creative"


def test_extract_explanation_query(extractor):
    query = "Explain what a database index is and when to use one"
    features = extractor.extract(query)
    assert features.is_explanation
    assert features.query_type.value == "explanation"


def test_extract_comparison_query(extractor):
    query = "Compare Python vs JavaScript for web development"
    features = extractor.extract(query)
    assert features.is_comparison
    assert features.query_type.value == "comparison"


def test_extract_simple_query(extractor):
    query = "Is four a number?"
    features = extractor.extract(query)
    assert features.has_question
    assert features.query_type.value == "general"


def test_constraint_detection(extractor):
    query = "Implement O(n) algorithm with O(1) space complexity"
    features = extractor.extract(query)
    assert features.has_constraints
    assert features.requires_optimization


def test_feature_vector_length(extractor):
    features = extractor.extract("test query")
    assert len(features.feature_vector) == 16


def test_similarity_same_query(extractor):
    f1 = extractor.extract("Write a function")
    f2 = extractor.extract("Write a function")
    sim = extractor.compute_similarity(f1, f2)
    assert sim >= 0.9


def test_similarity_different_queries(extractor):
    f1 = extractor.extract("sort array with bfs")
    f2 = extractor.extract("Explain quantum entanglement")
    sim = extractor.compute_similarity(f1, f2)
    assert sim < 1.0
    assert sim < extractor.compute_similarity(
        extractor.extract("sort array with bfs"),
        extractor.extract("sort array with bfs"),
    )
