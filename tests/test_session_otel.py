"""Task sessions (budgets/pins) and OpenTelemetry no-op safety."""

from modelhop.core.session import SessionManager, TaskSession
from modelhop.tracking import otel
from modelhop.tracking.otel import record_route, span


def test_session_budget_branches():
    s = TaskSession(budget=1.0, max_calls=2, token_ceiling=100)
    assert s.check_allow(est_cost=0.5) == (True, "")
    ok, reason = s.check_allow(est_cost=5.0)
    assert ok is False and "budget" in reason
    ok, reason = s.check_allow(est_tokens=500)
    assert ok is False and "token" in reason
    s.record(0.4, 10, 100)
    s.record(0.4, 10, 100)
    assert s.calls == 2
    ok, reason = s.check_allow()
    assert ok is False and "max calls" in reason
    assert s.exhausted() is True


def test_session_latency_ceiling_and_escalation():
    s = TaskSession(latency_ceiling_ms=150)
    assert s.exhausted() is False
    s.record(0.0, 0, 200, escalation="tier-up")
    assert s.escalations == ["tier-up"]
    assert s.exhausted() is True


def test_session_manager_crud():
    mgr = SessionManager()
    s = mgr.create(task_id="t", budget=2.0, pinned_model="m")
    assert s.task_id == "t"
    assert mgr.get(s.session_id) is s
    assert mgr.get("missing") is None
    ended = mgr.end(s.session_id)
    assert ended is s
    assert mgr.end(s.session_id) is None


def test_otel_record_route_never_raises():
    # No exporter configured: must be a silent no-op returning None.
    assert record_route("hi", "m", 0.9, 0.01) is None
    assert record_route("", "", 0.0, 0.0, degraded=True) is None


def test_otel_span_yields_without_backend():
    with span("modelhop.test", {"k": "v"}) as s:
        assert s is None


def test_otel_tracer_cached_or_none(monkeypatch):
    monkeypatch.setattr(otel, "_tracer", None, raising=False)
    monkeypatch.setattr(otel, "_provider_set", False, raising=False)
    assert record_route("q", "m", 0.5, 0.0) is None
