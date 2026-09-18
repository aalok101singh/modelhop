"""Append-only JSONL trace logger with atomic compaction (v1.1 W3).

Honest rehydration only: stored TraceEntry dicts are parsed back verbatim.
No fabricated fields. Optional ledger linkage via ledger_id.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..core.models import (
    ConfidenceResult,
    CostAnalysis,
    ProviderResponse,
    QueryAnalysis,
    RoutingDecision,
    TraceEntry,
)


class TraceLogger:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path("trace_log.jsonl")
        # Back-compat: if legacy .json path requested, honor it.
        self.history: List[TraceEntry] = []
        self._load_existing()

    def _load_existing(self) -> None:
        # Support both legacy trace_log.json (array envelope) and new JSONL.
        legacy = Path("trace_log.json")
        candidates = []
        if self.log_path.exists():
            candidates.append(self.log_path)
        if legacy.exists() and legacy.resolve() != self.log_path.resolve():
            candidates.append(legacy)
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # Try JSONL first.
            lines_ok = False
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # JSONL entries are full TraceEntry dicts.
                if isinstance(obj, dict) and "query_id" in obj and "analysis" in obj:
                    try:
                        self.history.append(TraceEntry(**obj))
                        lines_ok = True
                    except Exception:
                        continue
            if lines_ok:
                continue
            # Fall back to legacy envelope {"traces": [...] summary dicts}.
            # Honest rehydration: legacy summaries lack full fidelity, so we do
            # NOT fabricate full traces from them. Skip them (no fake entries).
            # Only migrate if entries already look like full traces.
            try:
                envelope = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(envelope, dict) and isinstance(envelope.get("traces"), list):
                for item in envelope["traces"]:
                    if isinstance(item, dict) and "analysis" in item and "decision" in item:
                        try:
                            self.history.append(TraceEntry(**item))
                        except Exception:
                            continue

    def log(
        self,
        query: str,
        analysis: QueryAnalysis,
        decision: RoutingDecision,
        response: ProviderResponse,
        confidence: ConfidenceResult,
        cost: CostAnalysis,
        fallback_used: bool = False,
        fallback_count: int = 0,
        ledger_id: Optional[str] = None,
        cache_hit: bool = False,
        degraded: bool = False,
        policy_version: str = "1",
    ) -> TraceEntry:
        # Strip raw_response before persistence (never serialized anyway via exclude=True).
        safe_response = response.model_copy(update={"raw_response": None})
        trace = TraceEntry(
            query_id=str(uuid.uuid4())[:8],
            query=query,
            timestamp=datetime.now(),
            analysis=analysis,
            decision=decision,
            response=safe_response,
            confidence=confidence,
            cost=cost,
            fallback_used=fallback_used,
            fallback_count=fallback_count,
            total_latency_ms=response.latency_ms,
            ledger_id=ledger_id,
            cache_hit=cache_hit,
            degraded=degraded or decision.degraded,
            policy_version=policy_version,
        )
        self.history.append(trace)
        self._append(trace)
        return trace

    def _append(self, trace: TraceEntry) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(trace.model_dump_json() + "\n")
        except OSError:
            pass

    def compact(self) -> None:
        """Atomically rewrite the log, dropping corrupt lines."""
        try:
            directory = str(self.log_path.parent) or "."
            fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    for trace in self.history:
                        f.write(trace.model_dump_json() + "\n")
                os.replace(tmp_path, str(self.log_path))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError:
            pass

    def get_history(self, limit: int = 20) -> List[TraceEntry]:
        return self.history[-limit:]

    def get_stats(self) -> dict:
        if not self.history:
            return {
                "total_queries": 0,
                "avg_complexity": 0,
                "avg_confidence": 0,
                "avg_latency_ms": 0,
                "fallback_rate": 0,
            }

        return {
            "total_queries": len(self.history),
            "avg_complexity": sum(t.analysis.complexity for t in self.history) / len(self.history),
            "avg_confidence": sum(t.confidence.score for t in self.history) / len(self.history),
            "avg_latency_ms": sum(t.total_latency_ms for t in self.history) / len(self.history),
            "fallback_rate": sum(1 for t in self.history if t.fallback_used)
            / len(self.history)
            * 100,
        }
