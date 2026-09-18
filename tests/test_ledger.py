"""W3: Ledger chain integrity + tamper detection + decay math + aux cost."""

import json

from modelhop.core.models import ModelConfig, ProviderResponse, QueryType, Tier
from modelhop.tracking.cost_tracker import CostTracker
from modelhop.tracking.ledger import DecisionLedger


def test_ledger_chain_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELHOP_STATE_KEY", "ledger-key")
    ledger = DecisionLedger(path=str(tmp_path / "ledger.jsonl"))
    ledger.append({"q": "a"})
    ledger.append({"q": "b"})
    ok, bad = ledger.verify_chain()
    assert ok and bad is None
    assert len(list(ledger.replay())) == 2


def test_ledger_tamper_detected(tmp_path, monkeypatch):
    monkeypatch.setenv("MODELHOP_STATE_KEY", "ledger-key")
    path = tmp_path / "ledger.jsonl"
    ledger = DecisionLedger(path=str(path))
    ledger.append({"q": "a"})
    # Tamper on disk.
    lines = path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[0])
    obj["payload"]["q"] = "evil"
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    ledger2 = DecisionLedger(path=str(path))
    ok, bad = ledger2.verify_chain()
    assert not ok and bad == 0


def test_decay_math_weighted(tmp_path):

    from modelhop.core.memory import ExperienceMemory
    from modelhop.core.performance import PerformanceTracker

    mem = ExperienceMemory(data_dir=str(tmp_path))
    tracker = PerformanceTracker(mem, data_dir=str(tmp_path))
    # Two outcomes same cell: second with weight 1.0.
    tracker.record_outcome("m", QueryType.GENERAL, quality=1.0, latency_ms=100, fallback_used=False)
    tracker.record_outcome("m", QueryType.GENERAL, quality=0.0, latency_ms=100, fallback_used=False)
    m = tracker.get_metrics("m", QueryType.GENERAL)
    assert m.sample_count == 2
    assert abs(m.avg_quality - 0.5) < 1e-6
    assert abs(float(m.weight_sum) - 2.0) < 1e-6


def test_aux_cost_accounting(tmp_path):
    free = ModelConfig(name="f", provider="x", model="f", tier=Tier.FREE)
    exp = ModelConfig(
        name="p",
        provider="y",
        model="p",
        tier=Tier.PREMIUM,
        cost_per_1k_input=0.03,
        cost_per_1k_output=0.06,
    )
    tracker = CostTracker(log_path=str(tmp_path / "c.json"), all_models=[free, exp])
    resp = ProviderResponse(
        content="a", model_used="f", provider="x", tokens_in=1000, tokens_out=500
    )
    analysis = tracker.calculate(resp, free)
    assert analysis.baseline_model == "p"
    assert analysis.aux_calls == 0
    # Record an aux call.
    aux = ProviderResponse(
        content="aux", model_used="p", provider="y", tokens_in=100, tokens_out=100
    )
    tracker.record_aux("groq", aux)
    assert tracker.aux_calls == 1
    assert tracker.aux_cost_total > 0
