import json
import os
from typing import List
from datetime import datetime

ADAPTIVE_FILE = "modelhop_adaptive.json"


class AdaptiveThreshold:
    """Self-adjusting confidence threshold based on recent outcomes."""

    def __init__(self, initial: float = 0.7, data_dir: str = None):
        self.threshold = initial
        self.initial = initial
        self.data_dir = data_dir or os.getcwd()
        self.recent_outcomes: List[float] = []
        self.history: List[float] = []
        self.window_size = 10
        self.min_threshold = 0.5
        self.max_threshold = 0.9
        self.adjustment_rate = 0.02
        self._load()

    def _get_path(self) -> str:
        return os.path.join(self.data_dir, ADAPTIVE_FILE)

    def _load(self):
        path = self._get_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.threshold = data.get("threshold", self.initial)
            self.history = data.get("history", [])[-200:]
            self.recent_outcomes = data.get("recent_outcomes", [])[-50:]
        except Exception:
            pass

    def _persist(self):
        path = self._get_path()
        data = {
            "threshold": self.threshold,
            "history": self.history[-200:],
            "recent_outcomes": self.recent_outcomes[-50:],
            "last_updated": datetime.now().isoformat(),
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def adjust(self, outcome_quality: float):
        self.recent_outcomes.append(outcome_quality)
        self.history.append(outcome_quality)

        if len(self.recent_outcomes) >= self.window_size:
            avg = sum(self.recent_outcomes[-self.window_size:]) / self.window_size

            if avg > 0.85:
                self.threshold = max(
                    self.min_threshold,
                    self.threshold - self.adjustment_rate
                )
            elif avg < 0.7:
                self.threshold = min(
                    self.max_threshold,
                    self.threshold + self.adjustment_rate
                )

            self.recent_outcomes = []

        self._persist()

    def get_threshold(self) -> float:
        return self.threshold

    def get_trend(self) -> str:
        if len(self.history) < 20:
            return "insufficient_data"

        recent = sum(self.history[-10:]) / 10
        older = sum(self.history[-20:-10]) / 10

        if recent > older + 0.05:
            return "improving"
        elif recent < older - 0.05:
            return "degrading"
        else:
            return "stable"

    def get_stats(self) -> dict:
        recent_avg = 0.0
        if self.recent_outcomes:
            recent_avg = sum(self.recent_outcomes) / len(self.recent_outcomes)

        history_avg = 0.0
        if self.history:
            history_avg = sum(self.history) / len(self.history)

        return {
            "threshold": self.threshold,
            "initial": self.initial,
            "trend": self.get_trend(),
            "recent_avg": recent_avg,
            "history_avg": history_avg,
            "total_samples": len(self.history),
        }
