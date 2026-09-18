"""Core unit coverage: health/circuit-breaker, secrets, decomposer, reasoning,
analyzer LLM paths, bandit extras, rollout harness, hop score.
"""

import random
from types import SimpleNamespace

import pytest

from modelhop.core.analyzer import QueryAnalyzer
from modelhop.core.decomposer import QueryDecomposer
from modelhop.core.health import CircuitBreaker, HealthRegistry
from modelhop.core.models import ComplexityLevel, QueryAnalysis, QueryType, Tier
from modelhop.core.policy.bandit import ContextualBandit, context_key
from modelhop.core.policy.engine import PolicyContext
from modelhop.core.reasoning import ReasoningEngine
from modelhop.core.secrets import (
    AwsSecretsManagerProvider,
    ChainedSecretsProvider,
    EnvSecretsProvider,
    FileSecretsProvider,
    VaultSecretsProvider,
    redact,
)
from modelhop.eval.harness import RolloutHarness
from modelhop.tracking.hop_score import HopScore


# -- health ---------------------------------------------------------------
def test_breaker_transient_threshold_and_recovery():
    b = CircuitBreaker(failure_threshold=3, recovery_timeout_s=0.0, half_open_max=1)
    assert b.allow("m") is True
    b.record_failure("m", transient=True)
    b.record_failure("m", transient=True)
    assert b.allow("m") is True
    b.record_failure("m", transient=True)
    # Recovery timeout 0 => next allow() flips to half-open and permits a probe.
    assert b.allow("m") is True
    assert b.state("m") == "half_open"
    b.record_success("m")
    assert b.state("m") == "closed"


def test_breaker_hard_failure_trips_immediately():
    b = CircuitBreaker(failure_threshold=5, recovery_timeout_s=3600.0)
    b.record_failure("m", transient=False)
    assert b.allow("m") is False
    assert b.state("m") == "open"


def test_breaker_half_open_probe_limit():
    b = CircuitBreaker(failure_threshold=1, recovery_timeout_s=0.0, half_open_max=1)
    b.record_failure("m", transient=True)
    assert b.allow("m") is True  # OPEN -> HALF_OPEN transition permits entry
    assert b.allow("m") is False  # opening probe counts against the budget
    assert b.allow("m") is False  # probe budget spent
    b.record_failure("m", transient=True)  # half-open failure re-opens
    assert b.state("m") in ("open", "half_open")


def test_registry_snapshot_and_rate_limits():
    r = HealthRegistry()
    for ms in (100, 200, 300, 400):
        r.record_success("m", ms)
    r.record_failure("m", RuntimeError("429 rate_limited slow down"))
    snap = r.snapshot("m")
    assert snap.p50_ms == 200
    assert snap.p95_ms == 300
    assert snap.rate_limit_hits == 1
    assert snap.fail_rate == pytest.approx(1 / 5)
    assert r.allow("m") is True
    assert HealthRegistry._is_transient(RuntimeError("connection timeout")) is True
    assert HealthRegistry._is_transient(RuntimeError("weird")) is False
    assert HealthRegistry._is_rate_limit(RuntimeError("Rate Limit exceeded")) is True


# -- secrets --------------------------------------------------------------
def test_redact_and_env(monkeypatch):
    assert redact("supersecret") == "***"
    monkeypatch.setenv("MH_TEST_X", "1")
    env = EnvSecretsProvider()
    assert env.get("MH_TEST_X") == "1"
    assert env.get("") is None
    assert env.require("MH_TEST_X") == "1"
    with pytest.raises(KeyError):
        env.require("MH_DEFINITELY_MISSING_VAR")
    assert "MH_TEST_X" in env.list_available()


def test_file_provider_json_yaml_missing(tmp_path):
    f = tmp_path / "s.json"
    f.write_text('{"A": "1"}', encoding="utf-8")
    p = FileSecretsProvider(str(f))
    assert p.get("A") == "1"
    assert p.require("A") == "1"
    with pytest.raises(KeyError):
        p.require("NOPE")
    assert p.list_available() == ["A"]
    y = tmp_path / "s.yaml"
    y.write_text("B: two\n", encoding="utf-8")
    assert FileSecretsProvider(str(y)).get("B") == "two"
    missing = FileSecretsProvider(str(tmp_path / "nope.json"))
    assert missing.get("A") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    assert FileSecretsProvider(str(bad)).get("A") is None


def test_chained_first_hit_wins():
    a = FileSecretsProvider("/nonexistent")
    b = SimpleNamespace(
        get=lambda n: "B!" if n == "K" else None,
        list_available=lambda: ["K"],
    )
    c = ChainedSecretsProvider([a, b])
    assert c.get("K") == "B!"
    assert c.get("MISSING") is None
    assert c.require("K") == "B!"
    with pytest.raises(KeyError):
        c.require("MISSING")
    assert c.list_available() == ["K"]


def test_chained_swallows_provider_errors():
    class Boom:
        def get(self, n):
            raise RuntimeError("down")

        def list_available(self):
            raise RuntimeError("down")

    c = ChainedSecretsProvider([Boom()])
    assert c.get("K") is None
    assert c.list_available() == []


def test_aws_vault_offline_safe(monkeypatch):
    aws = AwsSecretsManagerProvider(region="us-east-1")
    monkeypatch.setattr(aws, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("no")))
    assert aws.get("K") is None
    with pytest.raises(KeyError):
        aws.require("K")
    assert aws.list_available() == []
    vault = VaultSecretsProvider(url="http://127.0.0.1:1", token="t")
    monkeypatch.setattr(vault, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("no")))
    assert vault.get("secret/path:key") is None
    with pytest.raises(KeyError):
        vault.require("secret/path:key")
    assert vault.list_available() == []


# -- decomposer -----------------------------------------------------------
def test_decomposer_simple_passthrough(make_analysis):
    d = QueryDecomposer()
    out = d.decompose("hi there", make_analysis(complexity=0.2))
    assert len(out) == 1 and out[0].purpose == "complete"


def test_decomposer_splits_complex(make_analysis):
    d = QueryDecomposer()
    q = "Explain photosynthesis and write a program to test sorting"
    out = d.decompose(q, make_analysis(complexity=0.8))
    assert len(out) == 2
    purposes = {s.purpose for s in out}
    assert purposes & {"testing", "implementation", "explanation", "description"}


def test_decomposer_purposes():
    d = QueryDecomposer()
    assert d._determine_purpose("write a test for login") == "testing"
    assert d._determine_purpose("debug this code now") == "debugging"
    assert d._determine_purpose("implement quicksort") == "implementation"
    assert d._determine_purpose("why is the sky blue") == "reasoning"
    assert d._determine_purpose("how does raft work") == "explanation"
    assert d._determine_purpose("describe paris") == "description"
    assert d._determine_purpose("just chatting here") == "general"


def test_decomposer_synthesize():
    d = QueryDecomposer()
    assert d.synthesize([]) == ""
    assert d.synthesize([SimpleNamespace(content="only")]) == "only"
    assert d.synthesize(["a", "b"]) == "a\n\n---\n\nb"


def test_decomposer_sub_analysis_branches():
    d = QueryDecomposer()
    assert d._analyze_sub_query("write code to explain recursion").complexity == 0.7
    assert d._analyze_sub_query("write a script").capabilities_needed == ["coding"]
    assert d._analyze_sub_query("explain black holes").capabilities_needed == ["technical"]
    assert d._analyze_sub_query("hello there").capabilities_needed == ["general"]
    assert d._split_query("one thing only") == ["one thing only"]


# -- reasoning ------------------------------------------------------------
def test_reasoning_full_with_memory_and_performance(tmp_path, monkeypatch, make_analysis):
    monkeypatch.chdir(tmp_path)
    from modelhop.core.features import FeatureExtractor
    from modelhop.core.memory import ExperienceMemory
    from modelhop.core.models import RoutingDecision
    from modelhop.core.performance import PerformanceTracker

    mem = ExperienceMemory()
    perf = PerformanceTracker(mem)
    eng = ReasoningEngine(mem, perf)
    features = FeatureExtractor().extract("Write a Python function to sort a list quickly")
    analysis = make_analysis(complexity=0.8, caps=("coding",))
    from modelhop.core.models import ModelConfig

    model = ModelConfig(name="free-a", provider="x", model="free-a", tier=Tier.FREE)
    decision = RoutingDecision(model=model, tier=model.tier, reason="test reason")
    mem.record(
        "Write a Python function to sort a list", features, analysis, decision, 0.9, False, 50
    )
    for _ in range(3):
        perf.record_outcome("free-a", QueryType.IMPLEMENTATION, 0.9, 100, False)
    text = eng.explain("Write a Python function to sort a list", analysis, decision, features)
    assert "Selected: free-a" in text
    assert "Memory:" in text
    assert "Performance:" in text
    assert "Best historical:" in text
    short = eng.explain_short(decision)
    assert short == "free-a [FREE]"


def test_reasoning_infer_types():
    from modelhop.core.memory import ExperienceMemory
    from modelhop.core.performance import PerformanceTracker

    eng = ReasoningEngine(ExperienceMemory(), PerformanceTracker(ExperienceMemory()))

    def mk(caps, cx=0.5):
        return QueryAnalysis(
            complexity=cx, level=ComplexityLevel.MEDIUM, capabilities_needed=list(caps)
        )

    assert eng._infer_query_type(mk(["coding"])).value == "implementation"
    assert eng._infer_query_type(mk(["creative"])).value == "creative"
    assert eng._infer_query_type(mk(["technical"])).value == "explanation"
    assert eng._infer_query_type(mk(["general"], cx=0.9)).value == "implementation"
    assert eng._infer_query_type(mk(["general"], cx=0.2)).value == "general"


def test_reasoning_merged_prefix(tmp_path, monkeypatch, make_analysis, sample_models):
    monkeypatch.chdir(tmp_path)
    from modelhop.core.memory import ExperienceMemory
    from modelhop.core.models import RoutingDecision
    from modelhop.core.performance import PerformanceTracker

    eng = ReasoningEngine(ExperienceMemory(), PerformanceTracker(ExperienceMemory()))
    model = sample_models[0]
    text = eng.explain(
        "hi",
        make_analysis(),
        RoutingDecision(model=model, tier=model.tier, reason="r"),
        None,
        merged_reasoning="picked cheap",
    )
    assert text.startswith("[Engine] picked cheap")


# -- analyzer LLM paths ---------------------------------------------------
class _JudgeProvider:
    def __init__(self, content=None, exc=None):
        self.content = content
        self.exc = exc
        self.calls = 0

    async def generate(self, prompt, max_tokens=200, temperature=0.1):
        self.calls += 1
        if self.exc:
            raise self.exc
        return SimpleNamespace(content=self.content)


_GOOD = (
    '{"complexity": 0.8, "level": "complex", "capabilities_needed": ["coding"], '
    '"emotional_tone": "neutral", "estimated_tokens": 42, "reasoning": "judge says"}'
)


async def test_analyzer_llm_valid_and_cached():
    judge = _JudgeProvider(_GOOD)
    az = QueryAnalyzer([judge], enable_llm=True)
    out = await az.analyze("write a sort function")
    assert out.complexity == 0.8
    assert out.reasoning == "judge says"
    await az.analyze("write a sort function")
    assert judge.calls == 1


async def test_analyzer_auth_fallback():
    judge = _JudgeProvider(exc=RuntimeError("401 invalid api key"))
    az = QueryAnalyzer([judge], enable_llm=True)
    out = await az.analyze("hello")
    assert "auth error" in out.reasoning


async def test_analyzer_transient_fallback():
    judge = _JudgeProvider(exc=RuntimeError("connection timeout boom"))
    az = QueryAnalyzer([judge], enable_llm=True)
    out = await az.analyze("hello")
    assert "transient error" in out.reasoning


async def test_analyzer_strict_validation_fallback():
    judge = _JudgeProvider('{"complexity": 9.9, "level": "bogus"}')
    az = QueryAnalyzer([judge], enable_llm=True)
    out = await az.analyze("hello")
    assert "strict validation" in out.reasoning
    judge2 = _JudgeProvider("total garbage {{{")
    az2 = QueryAnalyzer([judge2], enable_llm=True)
    out2 = await az2.analyze("hello")
    assert "strict validation" in out2.reasoning


def test_analyzer_validate_schema_edges():
    az = QueryAnalyzer([], enable_llm=False)
    assert az._validate_schema("nope") is None
    assert az._validate_schema({"complexity": 2.0}) is None
    assert az._validate_schema({"complexity": 0.5, "level": "weird"}) is None
    assert (
        az._validate_schema({"complexity": 0.5, "level": "simple", "capabilities_needed": []})
        is None
    )
    assert (
        az._validate_schema(
            {"complexity": 0.5, "level": "simple", "capabilities_needed": ["telepathy"]}
        )
        is None
    )
    assert (
        az._validate_schema(
            {
                "complexity": 0.5,
                "level": "simple",
                "capabilities_needed": ["general"],
                "emotional_tone": "sleepy",
            }
        )
        is None
    )
    good = az._validate_schema(
        {"complexity": 0.3, "level": "simple", "capabilities_needed": ["FAQ"]}
    )
    assert good and good["complexity"] == 0.3


def test_analyzer_extract_json_and_cap():
    az = QueryAnalyzer([], enable_llm=False)
    from modelhop.core.analyzer import _cap

    assert _cap("short") == "short"
    assert _cap("x" * 3000).endswith("...[truncated]")
    out = az._extract_json('prefix {"complexity": 0.2} suffix')
    assert out["complexity"] == 0.2
    assert az._extract_json("no json here")["reasoning"].startswith("Failed to parse")


# -- bandit extras --------------------------------------------------------
def test_context_key_buckets():
    assert context_key("general", 0.1, "default") == "generalxsimplexdefault"
    assert context_key("general", 0.5, "default") == "generalxmediumxdefault"
    assert context_key("general", 0.9, "default") == "generalxcomplexxdefault"


def _bandit_models():
    from modelhop.core.models import ModelConfig

    return [
        ModelConfig(name="a", provider="x", model="a", tier=Tier.FREE),
        ModelConfig(name="b", provider="x", model="b", tier=Tier.FREE),
    ]


def test_bandit_linucb_and_feature_update():
    b = ContextualBandit(epsilon=0.0)
    models = _bandit_models()
    ctx = PolicyContext(query_type="general", complexity=0.2)
    pick, score, info = b.select_linucb(models, [0.5, 0.5])
    assert pick.name in ("a", "b") and info["method"] == "linucb"
    ctx2 = PolicyContext(query_type="general", complexity=0.2)
    ctx2.features = [0.5, 0.5]
    b.update(models[0], ctx2, 0.8)
    assert "a" in b._linucb
    with pytest.raises(AssertionError):
        b.select([], ctx)


def test_bandit_save_load_roundtrip():
    b = ContextualBandit()
    models = _bandit_models()
    ctx = PolicyContext(query_type="general", complexity=0.2)
    b.update(models[0], ctx, 0.9)

    class MemStore:
        def __init__(self):
            self.d = {}

        def save(self, path, data):
            self.d[path] = data

        def load(self, path):
            return self.d[path]

    store = MemStore()
    b.save(store)
    b2 = ContextualBandit.load(store)
    assert b2.stats == b.stats
    b3 = ContextualBandit.load(MemStore())  # missing path -> fresh
    assert b3.stats == {}


def test_bandit_seed_prior_shapes_selection():
    rng = random.Random(1)
    b = ContextualBandit(epsilon=0.0)
    models = _bandit_models()
    ctx = PolicyContext(query_type="general", complexity=0.2)
    b.seed_prior("b", context_key("general", 0.2, "default"), quality=1.0, samples=50)
    picks = [b.select(models, ctx, rng=rng)[0].name for _ in range(50)]
    assert picks.count("b") / len(picks) > 0.7


# -- harness + hopscore ---------------------------------------------------
async def test_harness_promote_and_hold():
    async def base(q):
        return SimpleNamespace(confidence=SimpleNamespace(score=0.5))

    async def cand(q):
        return SimpleNamespace(confidence=SimpleNamespace(score=0.9))

    h = RolloutHarness(canary_fraction=1.0)
    res = await h.run(["a", "b"], base, cand)
    assert res["shadow_ok"] == 2 and res["promote"] is True
    h2 = RolloutHarness(canary_fraction=0.0)
    res2 = await h2.run(["a"], base, cand)
    assert res2["canary_n"] == 0 and res2["promote"] is False


def test_hopscore_ratings_and_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = HopScore()
    assert h.get_score() == 100 and h.get_rating() == "excellent"
    h.update(True)
    h.update(False)
    h.update(False)
    assert h.get_score() == 33
    assert h.get_rating() == "poor"
    assert h.get_result().total_queries == 3
    import json

    (tmp_path / "trace_log.json").write_text(
        json.dumps({"traces": [{"confidence": 0.9}, {"confidence": 0.1}]}), encoding="utf-8"
    )
    h2 = HopScore()
    assert (h2.total_queries, h2.optimal_routes) == (2, 1)
    (tmp_path / "trace_log.json").write_text("garbage{{{", encoding="utf-8")
    assert HopScore().total_queries == 0
