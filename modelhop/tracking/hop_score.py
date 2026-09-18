import json
from pathlib import Path
from typing import Optional

from ..core.models import HopScoreResult

OPTIMAL_CONFIDENCE_DEFAULT = 0.7


def is_optimal_hop(is_confident: bool, savings: float = 0.0, would_have_cost: float = 0.0) -> bool:
    """User-approved optimal-hop rule: confident AND money saved.

    When no priced baseline exists (all-free config, would_have <= 0),
    any confident route counts as optimal — otherwise a free-only setup
    could never score.
    """
    if not is_confident:
        return False
    if (would_have_cost or 0.0) > 0:
        return (savings or 0.0) > 0
    return True


def _trace_optimal(obj: dict) -> Optional[bool]:
    """Best-effort optimal flag for one stored trace/summary dict."""
    conf = obj.get("confidence", 0)
    if isinstance(conf, dict):
        score = float(conf.get("score", 0) or 0)
        threshold = float(conf.get("threshold", 0) or 0) or OPTIMAL_CONFIDENCE_DEFAULT
    else:
        try:
            score = float(conf or 0)
        except (TypeError, ValueError):
            return None
        threshold = OPTIMAL_CONFIDENCE_DEFAULT
    cost = obj.get("cost", {}) or {}
    if isinstance(cost, dict):
        try:
            savings = float(cost.get("savings", 0) or 0)
        except (TypeError, ValueError):
            savings = 0.0
        try:
            would = float(cost.get("would_have_cost", 0) or 0)
        except (TypeError, ValueError):
            would = 0.0
    else:
        savings, would = 0.0, 0.0
    return is_optimal_hop(score >= threshold, savings, would)


class HopScore:
    def __init__(self, log_path: Optional[str] = None):
        # TraceLogger writes JSONL; legacy JSON envelope is still honored.
        self.log_path = Path(log_path) if log_path else Path("trace_log.jsonl")
        self.total_queries = 0
        self.optimal_routes = 0
        self._load_existing()

    def _load_existing(self) -> None:
        legacy = Path("trace_log.json")
        candidates = []
        if self.log_path.exists():
            candidates.append(self.log_path)
        try:
            same = (
                self.log_path.exists()
                and legacy.exists()
                and (legacy.resolve() == self.log_path.resolve())
            )
        except OSError:
            same = False
        if legacy.exists() and not same:
            candidates.append(legacy)
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            # Legacy envelope {"traces": [...]}: parse whole-file once so
            # inner objects are never double-counted line-by-line.
            try:
                envelope = json.loads(text)
            except json.JSONDecodeError:
                envelope = None
            if (
                isinstance(envelope, dict)
                and isinstance(envelope.get("traces"), list)
                and "query_id" not in envelope
            ):
                for item in envelope["traces"]:
                    if isinstance(item, dict):
                        flag = _trace_optimal(item)
                        if flag is not None:
                            self.total_queries += 1
                            if flag:
                                self.optimal_routes += 1
                continue
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and ("query_id" in obj or "confidence" in obj):
                    flag = _trace_optimal(obj)
                    if flag is not None:
                        self.total_queries += 1
                        if flag:
                            self.optimal_routes += 1
                    continue

    def update(self, was_optimal: bool) -> None:
        self.total_queries += 1
        if was_optimal:
            self.optimal_routes += 1

    def get_score(self) -> int:
        if self.total_queries == 0:
            return 100
        return int((self.optimal_routes / self.total_queries) * 100)

    def get_rating(self) -> str:
        score = self.get_score()
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "average"
        return "poor"

    def get_result(self) -> HopScoreResult:
        return HopScoreResult(
            score=self.get_score(),
            total_queries=self.total_queries,
            optimal_routes=self.optimal_routes,
            rating=self.get_rating(),
        )

    def get_stats(self) -> dict:
        return {
            "score": self.get_score(),
            "rating": self.get_rating(),
            "total_queries": self.total_queries,
            "optimal_routes": self.optimal_routes,
        }
