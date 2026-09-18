"""Provider health + circuit breaker (v1.1 W3)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class HealthSnap:
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    fail_rate: float = 0.0
    rate_limit_hits: int = 0
    state: str = "closed"


class CircuitBreaker:
    """CLOSED -> OPEN -> HALF_OPEN."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
        half_open_max: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.half_open_max = half_open_max
        self._failures: Dict[str, int] = defaultdict(int)
        self._state: Dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self._opened_at: Dict[str, float] = {}
        self._half_open_inflight: Dict[str, int] = defaultdict(int)

    def allow(self, key: str) -> bool:
        state = self._state[key]
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            opened = self._opened_at.get(key, 0.0)
            if (time.monotonic() - opened) >= self.recovery_timeout_s:
                self._state[key] = CircuitState.HALF_OPEN
                # The opening probe counts against the budget.
                self._half_open_inflight[key] = 1
                return True
            return False
        # HALF_OPEN: allow bounded probes.
        if self._half_open_inflight[key] < self.half_open_max:
            self._half_open_inflight[key] += 1
            return True
        return False

    def record_success(self, key: str) -> None:
        self._failures[key] = 0
        self._state[key] = CircuitState.CLOSED
        self._half_open_inflight[key] = 0
        self._opened_at.pop(key, None)

    def record_failure(self, key: str, transient: bool) -> None:
        if not transient:
            # Hard failures trip immediately.
            self._state[key] = CircuitState.OPEN
            self._opened_at[key] = time.monotonic()
            return
        self._failures[key] += 1
        if self._state[key] == CircuitState.HALF_OPEN:
            self._state[key] = CircuitState.OPEN
            self._opened_at[key] = time.monotonic()
            self._half_open_inflight[key] = 0
            return
        if self._failures[key] >= self.failure_threshold:
            self._state[key] = CircuitState.OPEN
            self._opened_at[key] = time.monotonic()

    def state(self, key: str) -> str:
        # Opportunistically transition OPEN -> HALF_OPEN on read.
        self.allow(key)
        return self._state[key].value


class HealthRegistry:
    def __init__(self):
        self._latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._outcomes: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._rate_limits: Dict[str, int] = defaultdict(int)
        self.breaker = CircuitBreaker()

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        msg = str(exc).lower()
        for token in ("429", "rate", "timeout", "temporar", "503", "502", "504", "overload"):
            if token in msg:
                return True
        return False

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "429" in msg or "rate limit" in msg or "rate_limited" in msg

    def record_success(self, key: str, latency_ms: int) -> None:
        self._latencies[key].append(float(latency_ms))
        self._outcomes[key].append(1.0)
        self.breaker.record_success(key)

    def record_failure(self, key: str, exc: Exception) -> None:
        self._outcomes[key].append(0.0)
        if self._is_rate_limit(exc):
            self._rate_limits[key] += 1
        self.breaker.record_failure(key, transient=self._is_transient(exc))

    def allow(self, key: str) -> bool:
        return self.breaker.allow(key)

    def snapshot(self, key: str) -> HealthSnap:
        lat = sorted(self._latencies.get(key, []))
        if lat:
            p50 = lat[int(0.5 * (len(lat) - 1))]
            p95 = lat[int(0.95 * (len(lat) - 1))]
        else:
            p50 = p95 = 0.0
        outcomes = list(self._outcomes.get(key, []))
        fail_rate = (sum(1.0 - o for o in outcomes) / len(outcomes)) if outcomes else 0.0
        return HealthSnap(
            p50_ms=p50,
            p95_ms=p95,
            fail_rate=fail_rate,
            rate_limit_hits=self._rate_limits.get(key, 0),
            state=self.breaker.state(key),
        )
