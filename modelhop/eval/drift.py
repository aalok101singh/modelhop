"""Feature/reward drift detection with auto-rollback (v1.1 W4)."""

from __future__ import annotations

from collections import deque
from typing import Deque


class DriftDetector:
    def __init__(self, window: int = 50, threshold: float = 0.15):
        self.window = window
        self.threshold = threshold
        self.baseline: Deque[float] = deque(maxlen=window)
        self.recent: Deque[float] = deque(maxlen=window)
        self.rolled_back = False

    def add_baseline(self, reward: float) -> None:
        self.baseline.append(float(reward))

    def add(self, reward: float) -> str:
        self.recent.append(float(reward))
        if len(self.baseline) < 10 or len(self.recent) < 10:
            return "insufficient_data"
        base_avg = sum(self.baseline) / len(self.baseline)
        recent_avg = sum(self.recent) / len(self.recent)
        if base_avg - recent_avg > self.threshold:
            self.rolled_back = True
            return "drift_rollback"
        if abs(recent_avg - base_avg) > self.threshold / 2:
            return "drift_warning"
        return "stable"
