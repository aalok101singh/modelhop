"""Tests for the simple Router (non-learning)."""

from modelhop.core.router import Router


def test_simple_routes_to_free(sample_models, make_analysis):
    router = Router(sample_models)
    decision = router.route(make_analysis(complexity=0.2))
    assert decision.tier.value == "free"


def test_complex_needs_advanced_caps_routes_to_premium(sample_models, make_analysis):
    router = Router(sample_models)
    decision = router.route(make_analysis(complexity=0.8, caps=("coding",)))
    assert decision.tier.value == "premium"


def test_medium_no_caps_routes_to_free(sample_models, make_analysis):
    router = Router(sample_models)
    decision = router.route(make_analysis(complexity=0.5, caps=("general",)))
    assert decision.tier.value == "free"


def test_neutral_complex_tries_free_first(sample_models, make_analysis):
    router = Router(sample_models)
    # neutral tone with complex query still tries free first
    analysis = make_analysis(complexity=0.7, caps=("general",))
    decision = router.route(analysis)
    assert decision.tier.value == "free"


def test_fallback_to_first_model_when_none_capable(sample_models, make_analysis):
    router = Router(sample_models)
    # Need a capability no model has
    analysis = make_analysis(complexity=0.5, caps=("nonexistent_cap",))
    decision = router.route(analysis)
    # Should fall back to first model
    assert decision.model is not None


def test_route_with_model_returns_named_model(sample_models, make_analysis):
    router = Router(sample_models)
    decision = router.route_with_model("premium-a", make_analysis())
    assert decision.model.name == "premium-a"
