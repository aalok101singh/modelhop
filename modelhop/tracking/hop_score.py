import json
from pathlib import Path
from typing import Optional
from ..core.models import HopScoreResult


class HopScore:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path("trace_log.json")
        self.total_queries = 0
        self.optimal_routes = 0
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r") as f:
                log = json.load(f)
            for trace in log.get("traces", []):
                self.total_queries += 1
                if trace.get("confidence", 0) >= 0.7:
                    self.optimal_routes += 1
        except Exception:
            pass

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
            rating=self.get_rating()
        )

    def get_stats(self) -> dict:
        return {
            "score": self.get_score(),
            "rating": self.get_rating(),
            "total_queries": self.total_queries,
            "optimal_routes": self.optimal_routes
        }
