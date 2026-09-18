"""W4: hub tamper, k-anonymity, policy spec, drift rollback."""

import json

import yaml

from modelhop.eval.drift import DriftDetector
from modelhop.hub.cards import publish_cards, verify_card


def test_unsigned_config_rejected(tmp_path):
    from modelhop.hub.hub import Hub

    cfg = {"name": "evil", "models": []}
    (tmp_path / "evil.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    hub = Hub(configs_path=str(tmp_path))
    assert hub.get_config("evil") is None
    assert hub.list_configs() == []


def test_tampered_sig_rejected(tmp_path, monkeypatch):
    from modelhop.hub.hub import Hub

    monkeypatch.setenv("MODELHOP_STATE_KEY", "card-key")
    cfg = {"name": "good", "models": [{"name": "a", "provider": "x", "model": "a", "tier": "free"}]}
    (tmp_path / "good.yaml").write_text(yaml.dump(cfg), encoding="utf-8")
    (tmp_path / "good.sig").write_text("bad-signature", encoding="utf-8")
    hub = Hub(configs_path=str(tmp_path))
    assert hub.get_config("good") is None


def test_k_anonymity_floor(tmp_path):
    from modelhop.core.models import Experience, QueryType

    exps = [
        Experience(
            model_name="m", query_type=QueryType.GENERAL, response_quality=0.9, latency_ms=100
        )
        for _ in range(3)
    ]
    cards = publish_cards(exps, k=5)
    assert cards == []
    exps5 = exps + [
        Experience(
            model_name="m", query_type=QueryType.GENERAL, response_quality=0.8, latency_ms=120
        )
        for _ in range(2)
    ]
    cards2 = publish_cards(exps5, k=5)
    assert len(cards2) == 1
    assert verify_card(cards2[0])
    # Allowlist: no raw text.
    assert "query" not in cards2[0].model_dump()


def test_policy_spec_validation():
    from pathlib import Path

    spec = Path(__file__).parent.parent / "spec" / "routing-policy.schema.json"
    assert spec.exists()
    data = json.loads(spec.read_text(encoding="utf-8"))
    assert data["title"] == "ModelHop Routing Policy"


def test_drift_rollback():
    det = DriftDetector(window=20, threshold=0.15)
    for _ in range(15):
        det.add_baseline(0.9)
    status = "stable"
    for _ in range(15):
        status = det.add(0.4)
    assert status == "drift_rollback"
    assert det.rolled_back
