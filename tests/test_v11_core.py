"""W1: calibration ECE, bandit regret, policy constraints, cache, verifier."""

import random

from modelhop.cache.exact import cache_key
from modelhop.cache.semantic import SemanticCache
from modelhop.core.calibration import Calibrator
from modelhop.core.models import ModelConfig, Tier
from modelhop.core.policy.bandit import ContextualBandit
from modelhop.core.policy.engine import (
    BudgetConstraint,
    CapabilityConstraint,
    PolicyContext,
    PolicyEngine,
    TrustConstraint,
)
from modelhop.core.reward import compute_reward
from modelhop.core.verifier.base import VerifierPipeline
from modelhop.core.verifier.schema import SchemaVerifier
from modelhop.eval.offline import doubly_robust, ips_estimate


def _models():
    return [
        ModelConfig(
            name="free-a",
            provider="x",
            model="free-a",
            tier=Tier.FREE,
            capabilities=["general"],
            cost_per_1k_input=0,
            cost_per_1k_output=0,
        ),
        ModelConfig(
            name="premium-a",
            provider="y",
            model="premium-a",
            tier=Tier.PREMIUM,
            capabilities=["general", "coding"],
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06,
        ),
    ]


def test_calibration_ece_low():
    cal = Calibrator()
    pairs = [(0.9, True)] * 20 + [(0.1, False)] * 20
    cal.fit(pairs)
    assert cal.ece() < 0.2
    assert 0.0 <= cal.transform(0.85) <= 1.0


def test_bandit_regret_synthetic():
    rng = random.Random(0)
    models = _models()
    bandit = ContextualBandit(epsilon=0.05)
    from modelhop.core.policy.engine import PolicyContext

    ctx = PolicyContext(query_type="general", complexity=0.2)
    # Premium is oracle (reward 1.0), free gives 0.0. Bandit should learn.
    rewards = {"free-a": 0.0, "premium-a": 1.0}
    for _ in range(200):
        pick, _, _ = bandit.select(models, ctx, rng=rng)
        bandit.update(pick, ctx, rewards[pick.name])
    # After learning, Thompson should favor premium most of the time.
    picks = [bandit.select(models, ctx, rng=rng)[0].name for _ in range(100)]
    premium_rate = sum(1 for p in picks if p == "premium-a") / len(picks)
    assert premium_rate > 0.6


def test_policy_constraints_filter():
    models = _models()
    engine = PolicyEngine(
        constraints=[TrustConstraint({}), CapabilityConstraint(), BudgetConstraint()]
    )
    ctx = PolicyContext(capabilities_needed=["coding"], cost_ceiling=0.0001)
    result = engine.evaluate(models, ctx)
    # Only premium has coding, but ceiling blocks it -> empty (fail-closed).
    assert result.eligible == []
    ctx2 = PolicyContext(capabilities_needed=["general"])
    result2 = engine.evaluate(models, ctx2)
    assert len(result2.eligible) == 2


def test_cache_correctness_and_privacy(tmp_path, monkeypatch):
    from modelhop.cache.exact import ExactCache

    # Never attempt embedding-model downloads (hermetic like other suites).
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    cache = ExactCache(path=str(tmp_path / "c.sqlite"))
    key = cache_key("Hello", "v1", "1", "default")
    assert cache.get(key) is None
    cache.put(key, {"response": "hi", "policy_version": "1"})
    assert cache.get(key)["response"] == "hi"
    # Semantic privacy: store_text=False never keeps raw text.
    sem = SemanticCache(threshold=0.5, store_text=False)
    sem.put("hello world", "secret answer", "m")
    hit = sem.get("hello world")
    assert hit is not None
    assert hit["response"] == ""


def test_verifier_gating():
    pipe = VerifierPipeline([SchemaVerifier(pattern=r"hello")])
    ok = pipe.verify("q", "hello world")
    assert ok.passed
    bad = pipe.verify("q", "goodbye")
    assert not bad.passed


def test_reward_weights():
    r = compute_reward(
        quality=1.0, cost=0.0, latency_ms=100, verifier_pass=True, fallback=False, retries=0
    )
    r2 = compute_reward(
        quality=0.2, cost=0.09, latency_ms=4000, verifier_pass=False, fallback=True, retries=2
    )
    assert r > r2


def test_offline_estimators():
    logged = [
        {"reward": 1.0, "propensity": 0.5},
        {"reward": 0.0, "propensity": 0.5},
    ]
    assert abs(ips_estimate(logged, lambda row: 0.5) - 0.5) < 1e-6
    assert abs(doubly_robust(logged, lambda row: 0.5, lambda row: 0.5) - 0.5) < 1e-6
