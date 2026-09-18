"""TraceLogger: append-only JSONL, honest rehydration, compaction, legacy support."""

import json

from modelhop.tracking.trace_logger import TraceLogger


def _parts(make_analysis, sample_models):
    from modelhop.core.models import (
        ConfidenceResult,
        CostAnalysis,
        ProviderResponse,
        RoutingDecision,
    )

    model = sample_models[0]
    return dict(
        query="trace test query",
        analysis=make_analysis(),
        decision=RoutingDecision(model=model, tier=model.tier, reason="test"),
        response=ProviderResponse(
            content="ans", model_used=model.name, provider="x", tokens_in=10, tokens_out=5
        ),
        confidence=ConfidenceResult(score=0.8, is_confident=True, threshold=0.7),
        cost=CostAnalysis(
            actual_cost=0.0,
            would_have_cost=0.01,
            savings=0.01,
            savings_percentage=100.0,
            model_used=model.name,
            tier=model.tier.value,
        ),
    )


def test_empty_stats(tmp_path):
    tl = TraceLogger(log_path=str(tmp_path / "t.jsonl"))
    assert tl.get_history() == []
    stats = tl.get_stats()
    assert stats["total_queries"] == 0
    assert stats["fallback_rate"] == 0


def test_log_appends_and_stats(tmp_path, make_analysis, sample_models):
    tl = TraceLogger(log_path=str(tmp_path / "t.jsonl"))
    trace = tl.log(**_parts(make_analysis, sample_models), ledger_id="L1")
    assert trace.ledger_id == "L1"
    assert len(tl.get_history()) == 1
    lines = (tmp_path / "t.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["query"] == "trace test query"
    stats = tl.get_stats()
    assert stats["total_queries"] == 1
    assert stats["avg_confidence"] == 0.8


def test_reload_roundtrip(tmp_path, make_analysis, sample_models):
    path = str(tmp_path / "t.jsonl")
    tl = TraceLogger(log_path=path)
    tl.log(**_parts(make_analysis, sample_models))
    tl.log(**_parts(make_analysis, sample_models), fallback_used=True)
    tl2 = TraceLogger(log_path=path)
    assert len(tl2.get_history()) == 2
    assert tl2.get_stats()["fallback_rate"] == 50.0
    assert tl2.get_history(limit=1)[0].fallback_used is True


def test_corrupt_lines_skipped(tmp_path, make_analysis, sample_models):
    path = tmp_path / "t.jsonl"
    tl = TraceLogger(log_path=str(path))
    tl.log(**_parts(make_analysis, sample_models))
    with open(path, "a", encoding="utf-8") as f:
        f.write("this is not json\n")
        f.write('{"partial": true}\n')
    tl2 = TraceLogger(log_path=str(path))
    assert len(tl2.get_history()) == 1
    tl2.compact()
    assert len((path).read_text(encoding="utf-8").strip().splitlines()) == 1


def test_legacy_envelope_migration(tmp_path, monkeypatch, make_analysis, sample_models):
    monkeypatch.chdir(tmp_path)
    tl = TraceLogger(log_path=str(tmp_path / "new.jsonl"))
    trace = tl.log(**_parts(make_analysis, sample_models))
    legacy = {"traces": [json.loads(trace.model_dump_json())]}
    (tmp_path / "trace_log.json").write_text(json.dumps(legacy), encoding="utf-8")
    tl2 = TraceLogger(log_path=str(tmp_path / "other.jsonl"))
    assert any(t.query_id == trace.query_id for t in tl2.get_history())


def test_legacy_summaries_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trace_log.json").write_text(
        json.dumps({"traces": [{"query": "q", "model": "m"}]}), encoding="utf-8"
    )
    tl = TraceLogger(log_path=str(tmp_path / "n.jsonl"))
    assert tl.get_history() == []
