"""Tests for the 21 Qodo review findings (PR #4). Hermetic: tmp cwd, fakes only."""

import pytest

from modelhop import ModelHop
from modelhop.cache.semantic import SemanticCache
from modelhop.core.models import (
    ModelConfig,
    ProviderResponse,
    QueryFeatures,
    RoutingDecision,
    Tier,
    TrustProfile,
)
from modelhop.core.trust import filter_by_trust


class FakeProvider:
    async def generate(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        return ProviderResponse(
            content="agent answer " * 40,
            model_used="fake",
            provider="fake",
            tokens_in=10,
            tokens_out=60,
            latency_ms=40,
        )


@pytest.fixture
def qmh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    mh = ModelHop()
    mh.registry._providers = {m.name: FakeProvider() for m in mh.models}
    return mh


def _model(name, zdr=False, jurisdiction=None):
    return ModelConfig(
        name=name,
        provider="x",
        model=name,
        tier=Tier.FREE,
        capabilities=["general"],
        trust=TrustProfile(zdr=zdr, jurisdiction=jurisdiction),
    )


# -- Q3: zdr alias ----------------------------------------------------------
def test_zdr_alias_enforced():
    models = [_model("a", zdr=False), _model("b", zdr=True)]
    eligible, _ = filter_by_trust(models, {}, {"zdr": True})
    assert [m.name for m in eligible] == ["b"]
    eligible, _ = filter_by_trust(models, {}, {"require_zdr": True})
    assert [m.name for m in eligible] == ["b"]
    eligible, _ = filter_by_trust(models, {}, {})
    assert len(eligible) == 2


# -- Q11: jurisdiction allowlist strict -------------------------------------
def test_jurisdiction_unknown_rejected_when_allowlist():
    models = [_model("u"), _model("eu", jurisdiction="EU"), _model("us", jurisdiction="US")]
    eligible, _ = filter_by_trust(models, {}, {"allowed_jurisdictions": ["EU"]})
    assert [m.name for m in eligible] == ["eu"]
    # No allowlist requested: permissive as documented.
    eligible, _ = filter_by_trust(models, {}, {})
    assert len(eligible) == 3


# -- Q5: task sessions reused -----------------------------------------------
def test_task_session_reused_and_accumulates():
    from modelhop.core.session import SessionManager

    sm = SessionManager()
    s1 = sm.create(task_id="t1", budget=1.0)
    s1.record(0.4, 10, 5)
    s2 = sm.get_by_task("t1")
    assert s2 is s1
    assert s2.spent == 0.4
    assert sm.get_by_task("nope") is None


# -- Q21: exact-match .env surgery ------------------------------------------
def test_env_key_exact_match(tmp_path, monkeypatch):
    from modelhop.cli.commands import setup as su

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        'GROQ_API_KEY="a"\nGROQ_API_KEY_BACKUP="keep"\n# comment\n\n', encoding="utf-8"
    )
    monkeypatch.setattr(su, "ENV_PATH", tmp_path / ".env")
    su._remove_env_keys(["GROQ_API_KEY"])
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GROQ_API_KEY_BACKUP" in text
    assert "GROQ_API_KEY=" not in text.replace("GROQ_API_KEY_BACKUP", "")
    su._save_env({"GROQ_API_KEY": "b"})
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert text.count("GROQ_API_KEY_BACKUP") == 1
    assert 'GROQ_API_KEY="b"' in text


# -- Q9: semantic tenant isolation ------------------------------------------
def test_semantic_tenant_isolation():
    sem = SemanticCache(threshold=0.1)
    sem.put("same question", "tenant-a answer", "m", tenant="a")
    assert sem.get("same question", tenant="b") is None
    hit = sem.get("same question", tenant="a")
    assert hit and hit["response"] == "tenant-a answer"


# -- Q10: trust-aware cache ---------------------------------------------------
def test_trust_digest_splits_cache_keys():
    from modelhop import _trust_digest
    from modelhop.cache.exact import cache_key

    assert _trust_digest({}) == _trust_digest({})
    assert _trust_digest({"require_zdr": True}) != _trust_digest({})
    k1 = cache_key("q", "v", "1", "default", _trust_digest({}))
    k2 = cache_key("q", "v", "1", "default", _trust_digest({"require_zdr": True}))
    assert k1 != k2
    # Legacy 4-arg form still works.
    assert cache_key("q", "v", "1", "default")


def test_cache_hit_refiltered_by_trust(qmh, make_analysis, sample_models):
    from modelhop import _CacheTrustMiss

    model = sample_models[0]  # default trust: zdr False
    decision = RoutingDecision(model=model, tier=model.tier, reason="t")
    hit = {"response": "cached", "model": model.name, "policy_version": "1"}
    ok = qmh._result_from_cache(hit, decision, "r", QueryFeatures(), make_analysis(), query="q")
    assert ok.cached is True
    with pytest.raises(_CacheTrustMiss):
        qmh._result_from_cache(
            hit,
            decision,
            "r",
            QueryFeatures(),
            make_analysis(),
            query="q",
            trust_required={"require_zdr": True},
        )


# -- Q4: no_raw_cache gates both stores --------------------------------------
def test_no_raw_cache_skips_all_persistence(qmh):
    import asyncio
    import sqlite3

    def row_count():
        conn = sqlite3.connect(str(qmh.exact_cache.path))
        try:
            return conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        finally:
            conn.close()

    asyncio.run(qmh.route("ordinary persisted query"))
    assert qmh.exact_cache is not None
    assert row_count() == 1
    # Different query (cache miss) under no_raw_cache: generate but persist nothing.
    asyncio.run(qmh.route("private unpersisted query", trust_required={"no_raw_cache": True}))
    assert row_count() == 1


# -- Q15/Q17: cache-hit accounting + trace linkage -----------------------------
def test_cache_hit_logged_and_linked(qmh):
    import asyncio

    r1 = asyncio.run(qmh.route("repeat after me please"))
    assert r1.cached is False
    r2 = asyncio.run(qmh.route("repeat after me please"))
    assert r2.cached is True
    traces = qmh.trace_logger.history
    assert len(traces) == 2
    assert traces[1].cache_hit is True
    assert r1.ledger_id and traces[0].ledger_id == r1.ledger_id
    assert qmh.hop_score.total_queries == 2


# -- Q6: aux single counting ---------------------------------------------------
def test_aux_counted_once(tmp_path):
    from modelhop.core.models import ProviderResponse as PR
    from modelhop.tracking.cost_tracker import CostTracker

    tracker = CostTracker(log_path=str(tmp_path / "c.json"))
    resp = PR(content="a", model_used="m", provider="x", tokens_in=100, tokens_out=100)
    a1 = tracker.calculate(
        resp, _model("m"), extra_actual=0.05, extra_would=0.05, extra_aux_calls=2
    )
    assert (a1.aux_calls, a1.aux_cost) == (2, 0.05)
    a2 = tracker.calculate(
        resp, _model("m"), extra_actual=0.05, extra_would=0.05, extra_aux_calls=2
    )
    assert (a2.aux_calls, a2.aux_cost) == (2, 0.05)
    assert (tracker.aux_calls, tracker.aux_cost_total) == (4, 0.10)


# -- Q8: ledger failure raises --------------------------------------------------
def test_ledger_append_raises_when_unwritable(tmp_path):
    from modelhop.tracking.ledger import DecisionLedger

    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    ledger = DecisionLedger(path=str(blocker / "ledger.jsonl"))
    with pytest.raises(OSError):
        ledger.append({"q": 1})
    assert len(ledger) == 0


# -- Q20: zero/missing propensity excluded --------------------------------------
def test_zero_propensity_excluded():
    from modelhop.eval.offline import doubly_robust, ips_estimate

    rows = [
        {"reward": 1.0, "propensity": 0.5},
        {"reward": 1.0, "propensity": 0.0},
        {"reward": 1.0},
    ]
    # Only the supported row counts (2.0/1): zero-support and missing
    # propensity rows are excluded, never fabricated as 1.0.
    assert ips_estimate(rows, lambda r: 1.0) == 2.0
    assert doubly_robust(rows, lambda r: 1.0, lambda r: 0.0) == 2.0


# -- Q13: sub vetting keeps safety gates, tolerates capability gaps ------------
def test_decomposed_tolerates_capability_gap(qmh):
    import asyncio

    # 'technical' is in no stock model's capabilities; decomposition must
    # still complete (trust/budget/health stay hard, capability best-effort).
    r = asyncio.run(
        qmh.route("Explain photosynthesis in detail and write a Python function to sort a list")
    )
    assert r.response and r.model


# -- Q2: fallbacks stay in the eligible set --------------------------------------
def test_fallback_skips_ineligible_models(qmh):
    free = next(m for m in qmh.models if m.tier.value == "free")
    decision = RoutingDecision(model=free, tier=free.tier, reason="t")
    nxt = qmh._next_fallback_decision(decision, {free.name}, eligible_names={"openai-gpt-4"})
    assert nxt is None or nxt.model.name == "openai-gpt-4"
    assert qmh._next_fallback_decision(decision, {free.name}, eligible_names=set()) is None


# -- Q12: serve explicit-model policy gate -----------------------------------------
def test_serve_explicit_model_trust_refused(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from modelhop.core.models import TrustProfile
    from modelhop.serve.app import create_app

    monkeypatch.chdir(tmp_path)
    model = ModelConfig(
        name="premium-x",
        provider="x",
        model="premium-x",
        tier=Tier.PREMIUM,
        capabilities=["general"],
        trust=TrustProfile(zdr=False),
    )

    async def gen(query, **kw):
        return ProviderResponse(content="x", model_used="premium-x", provider="x")

    mh = SimpleNamespace(
        models=[model],
        registry=SimpleNamespace(
            get_provider=lambda name: (
                SimpleNamespace(generate=gen) if name == "premium-x" else None
            ),
            get_model=lambda name: model if name == "premium-x" else None,
        ),
        route=None,
        secrets=SimpleNamespace(get=lambda name: None),
        trust_policy={"require_zdr": True},
        health=None,
    )
    client = TestClient(create_app(mh))
    r = client.post(
        "/v1/chat/completions",
        json={"model": "premium-x", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403


# -- Q18/Q19: hub download dirs + mandatory validation ------------------------------
def test_hub_download_keeps_subdirs(tmp_path, monkeypatch):
    from modelhop.hub.hub import Hub

    monkeypatch.chdir(tmp_path)
    hub = Hub()
    assert hub.download_config("support-bot", "sub/dir/team.yaml") is True
    assert (tmp_path / "sub" / "dir" / "team.yaml").exists()
    # Escape attempts stay confined.
    assert hub.download_config("support-bot", "../../evil.yaml") is True
    assert not (tmp_path.parent / "evil.yaml").exists()


def test_hub_rejects_malformed_config():
    from modelhop.hub.hub import Hub

    hub = Hub()
    assert hub._validate_schema({"models": [{"name": "a"}]}) is False
    assert hub._validate_schema({"models": "nope"}) is False
    assert hub._validate_schema({}) is False
    assert (
        hub._validate_schema(
            {
                "models": [
                    {
                        "name": "a",
                        "provider": "x",
                        "model": "x",
                        "tier": "free",
                    }
                ]
            }
        )
        is True
    )


# -- Q1: serve auth fails closed -----------------------------------------------------
def test_serve_auth_backend_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from modelhop.serve.app import create_app

    monkeypatch.chdir(tmp_path)
    model = ModelConfig(name="m", provider="x", model="m", tier=Tier.FREE, capabilities=["general"])
    mh = SimpleNamespace(
        models=[model],
        registry=SimpleNamespace(get_provider=lambda n: None, get_model=lambda n: None),
        route=None,
        secrets=SimpleNamespace(get=lambda name: (_ for _ in ()).throw(RuntimeError("vault down"))),
        trust_policy={},
        health=None,
    )
    client = TestClient(create_app(mh))
    assert client.get("/v1/models").status_code == 503
