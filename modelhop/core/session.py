"""Task-scoped sessions with budgets and coherence (v1.1 W1)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskSession:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    task_id: Optional[str] = None
    budget: Optional[float] = None
    max_calls: Optional[int] = None
    token_ceiling: Optional[int] = None
    latency_ceiling_ms: Optional[int] = None
    pinned_model: Optional[str] = None
    spent: float = 0.0
    calls: int = 0
    tokens: int = 0
    latency_ms: int = 0
    escalations: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def check_allow(self, est_cost: float = 0.0, est_tokens: int = 0) -> tuple[bool, str]:
        if self.max_calls is not None and self.calls >= self.max_calls:
            return False, "max calls exceeded"
        if self.budget is not None and (self.spent + est_cost) > self.budget:
            return False, "budget exceeded"
        if self.token_ceiling is not None and (self.tokens + est_tokens) > self.token_ceiling:
            return False, "token ceiling exceeded"
        return True, ""

    def record(self, cost: float, tokens: int, latency_ms: int, escalation: str = "") -> None:
        self.spent += float(cost or 0.0)
        self.calls += 1
        self.tokens += int(tokens or 0)
        self.latency_ms += int(latency_ms or 0)
        if escalation:
            self.escalations.append(escalation)

    def exhausted(self) -> bool:
        ok, _ = self.check_allow()
        if not ok:
            return True
        if self.latency_ceiling_ms is not None and self.latency_ms >= self.latency_ceiling_ms:
            return True
        return False


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, TaskSession] = {}

    def create(
        self,
        task_id: Optional[str] = None,
        budget: Optional[float] = None,
        max_calls: Optional[int] = None,
        token_ceiling: Optional[int] = None,
        latency_ceiling_ms: Optional[int] = None,
        pinned_model: Optional[str] = None,
    ) -> TaskSession:
        session = TaskSession(
            task_id=task_id,
            budget=budget,
            max_calls=max_calls,
            token_ceiling=token_ceiling,
            latency_ceiling_ms=latency_ceiling_ms,
            pinned_model=pinned_model,
        )
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[TaskSession]:
        return self.sessions.get(session_id)

    def end(self, session_id: str) -> Optional[TaskSession]:
        return self.sessions.pop(session_id, None)
