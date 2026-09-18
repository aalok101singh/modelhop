"""W3: Trust-policy enforcement + tamper rejection + secrets isolation."""

import json

import pytest

from modelhop.core.models import ModelConfig, Tier, TrustProfile
from modelhop.core.persistence import SignedStore, StateIntegrityError
from modelhop.core.trust import TrustViolation, filter_by_trust


def _model(name, **trust_kwargs):
    trust = TrustProfile(**trust_kwargs)
    return ModelConfig(name=name, provider="x", model=name, tier=Tier.FREE, trust=trust)


def test_trust_permissive_by_default():
    models = [_model("a"), _model("b")]
    eligible, _ = filter_by_trust(models, {}, {})
    assert len(eligible) == 2


def test_trust_zdr_enforced():
    models = [_model("a", zdr=False), _model("b", zdr=True)]
    eligible, excluded = filter_by_trust(models, {"require_zdr": True}, {})
    assert [m.name for m in eligible] == ["b"]
    assert excluded


def test_trust_no_candidate_raises_in_router():
    from modelhop.core.models import ComplexityLevel, QueryAnalysis
    from modelhop.core.router import Router

    models = [_model("a", zdr=False)]
    router = Router(models, trust_policy={"require_zdr": True})
    analysis = QueryAnalysis(complexity=0.2, level=ComplexityLevel.SIMPLE)
    with pytest.raises(TrustViolation):
        router.route(analysis)


def test_signed_store_tamper_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELHOP_STATE_KEY", "test-key-123")
    store = SignedStore(schema_version=1)
    path = str(tmp_path / "state.json")
    store.save(path, {"a": 1})
    # Tamper.
    with open(path, "r", encoding="utf-8") as f:
        env = json.load(f)
    env["payload"]["a"] = 2
    with open(path, "w", encoding="utf-8") as f:
        json.dump(env, f)
    with pytest.raises(StateIntegrityError):
        store.load(path)


def test_signed_store_legacy_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELHOP_STATE_KEY", "test-key-123")
    path = str(tmp_path / "legacy.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"experiences": []}, f)
    store = SignedStore(schema_version=1)
    data = store.load(path)
    assert data == {"experiences": []}
    # Re-sign.
    store.save(path, data)
    assert store.load(path) == data


def test_secret_isolation_no_leak(monkeypatch):
    monkeypatch.setenv("MY_SECRET_KEY", "super-secret-value")
    from modelhop.core.secrets import EnvSecretsProvider, redact

    p = EnvSecretsProvider()
    assert p.get("MY_SECRET_KEY") == "super-secret-value"
    assert redact("super-secret-value") == "***"
    # Keys never in traces: ProviderResponse excludes raw, CostAnalysis has no secrets.
    from modelhop.core.models import ProviderResponse

    pr = ProviderResponse(content="hi", model_used="m", provider="x")
    dumped = pr.model_dump()
    assert "super-secret-value" not in str(dumped)
    assert "raw_response" not in dumped
