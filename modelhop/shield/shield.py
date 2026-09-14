from typing import List

from ..core.models import ShieldStatus, TraceEntry


class Shield:
    def __init__(self, quality_threshold: float = 0.8):
        self.quality_threshold = quality_threshold
        self.history: List[TraceEntry] = []
        self.alerts: List[str] = []
        self.adjustments: int = 0

    def check_quality(self, trace: TraceEntry) -> bool:
        self.history.append(trace)

        if trace.confidence.score < self.quality_threshold:
            alert = (
                f"Low confidence: {trace.confidence.score:.2f} "
                f"< {self.quality_threshold} "
                f"(query: {trace.query[:50]}...)"
            )
            self.alerts.append(alert)
            return False

        if self._detect_degradation():
            alert = "Quality degradation detected in recent queries"
            self.alerts.append(alert)
            return False

        return True

    def _detect_degradation(self) -> bool:
        if len(self.history) < 10:
            return False

        recent = self.history[-5:]
        previous = self.history[-10:-5]

        recent_avg = sum(t.confidence.score for t in recent) / len(recent)
        previous_avg = sum(t.confidence.score for t in previous) / len(previous)

        return (previous_avg - recent_avg) > 0.1

    def get_status(self) -> ShieldStatus:
        if not self.history:
            return ShieldStatus(
                active=True,
                quality_score=1.0,
                consensus_rate=1.0,
                alerts=[],
                adjustments_today=0
            )

        quality_score = sum(
            t.confidence.score for t in self.history
        ) / len(self.history)

        consensus_count = sum(
            1 for t in self.history
            if t.confidence.consensus_score is not None
        )
        consensus_rate = consensus_count / len(self.history) if self.history else 1.0

        return ShieldStatus(
            active=True,
            quality_score=quality_score,
            consensus_rate=consensus_rate,
            alerts=self.alerts[-5:],
            adjustments_today=self.adjustments
        )

    def get_recommendations(self) -> List[str]:
        recommendations = []
        status = self.get_status()

        if status.quality_score < 0.8:
            recommendations.append(
                "Consider lowering confidence threshold to route more queries to premium models"
            )

        if self._detect_degradation():
            recommendations.append(
                "Quality is degrading. Check provider status or adjust routing rules"
            )

        if len(self.alerts) > 10:
            recommendations.append(
                "High alert count. Review routing configuration"
            )

        return recommendations
