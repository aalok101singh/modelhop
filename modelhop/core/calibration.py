"""Isotonic (PAV) calibrator with ECE (v1.1 W1)."""

from __future__ import annotations

from typing import List


class Calibrator:
    def __init__(self):
        self.thresholds: List[float] = []
        self.values: List[float] = []
        self._ece: float | None = None
        self._n: int = 0

    def fit(self, pairs: list[tuple[float, bool]]) -> None:
        """Fit isotonic mapping; identity fallback when data is sparse."""
        self._n = len(pairs)
        if len(pairs) < 10:
            self.thresholds = []
            self.values = []
            self._ece = None
            return
        # Sort by score.
        ordered = sorted(((float(s), 1.0 if y else 0.0) for s, y in pairs), key=lambda x: x[0])
        # PAV: pool adjacent violators into blocks with (sum, count, score_avg).
        blocks: list[dict] = []
        for score, label in ordered:
            blocks.append({"scores": [score], "sum": label, "count": 1})
            while len(blocks) >= 2 and (blocks[-2]["sum"] / blocks[-2]["count"]) > (
                blocks[-1]["sum"] / blocks[-1]["count"]
            ):
                merged = {
                    "scores": blocks[-2]["scores"] + blocks[-1]["scores"],
                    "sum": blocks[-2]["sum"] + blocks[-1]["sum"],
                    "count": blocks[-2]["count"] + blocks[-1]["count"],
                }
                blocks = blocks[:-2] + [merged]
        self.thresholds = [min(b["scores"]) for b in blocks]
        self.values = [b["sum"] / b["count"] for b in blocks]
        self._ece = self._compute_ece(pairs, bins=10)

    def transform(self, score: float) -> float:
        if not self.thresholds:
            return max(0.0, min(1.0, float(score)))
        # Stepwise isotonic: last threshold <= score.
        out = self.values[0]
        for t, v in zip(self.thresholds, self.values):
            if score >= t:
                out = v
            else:
                break
        return max(0.0, min(1.0, float(out)))

    def ece(self, bins: int = 10) -> float:
        if self._ece is not None and bins == 10:
            return self._ece
        return 0.0

    def _compute_ece(self, pairs: list[tuple[float, bool]], bins: int = 10) -> float:
        if not pairs:
            return 0.0
        buckets: list[list[float]] = [[] for _ in range(bins)]
        labels: list[list[float]] = [[] for _ in range(bins)]
        for s, y in pairs:
            cal = self.transform(float(s))
            idx = min(bins - 1, int(cal * bins))
            buckets[idx].append(cal)
            labels[idx].append(1.0 if y else 0.0)
        ece = 0.0
        n = len(pairs)
        for bucket, bucket_labels in zip(buckets, labels):
            if not bucket:
                continue
            acc = sum(bucket_labels) / len(bucket_labels)
            conf = sum(bucket) / len(bucket)
            ece += abs(acc - conf) * (len(bucket) / n)
        return ece

    def save(self, store) -> None:
        store.save(
            "modelhop_calibrator.json",
            {
                "thresholds": self.thresholds,
                "values": self.values,
                "ece": self._ece,
                "n": self._n,
            },
        )

    @classmethod
    def load(cls, store) -> "Calibrator":
        from .persistence import StateIntegrityError

        cal = cls()
        try:
            data = store.load("modelhop_calibrator.json")
        except (StateIntegrityError, Exception):
            return cal
        if not isinstance(data, dict):
            return cal
        try:
            cal.thresholds = list(data.get("thresholds", []))
            cal.values = list(data.get("values", []))
            cal._ece = data.get("ece")
            cal._n = int(data.get("n", 0))
        except Exception:
            pass
        return cal
