from datetime import datetime
from typing import List, Optional

from ..core.models import ShieldStatus, TraceEntry

MAX_ALERTS = 100
SHIELD_FILE = "modelhop_shield.json"


class Shield:
    """Quality monitoring rebuilt from the signed ledger; persisted, bounded alerts."""

    def __init__(self, quality_threshold: float = 0.8, data_dir: Optional[str] = None):
        import os

        self.quality_threshold = quality_threshold
        self.data_dir = data_dir or os.getcwd()
        self.history: List[TraceEntry] = []
        self.alerts: List[str] = []
        self.adjustments: int = 0
        self._load()
        # Rebuild from signed ledger when available (tamper-evident ground truth).
        try:
            self.rebuild_from_ledger()
        except Exception:
            pass

    def _path(self) -> str:
        import os

        return os.path.join(self.data_dir, SHIELD_FILE)

    def _store(self):
        from ..core.persistence import SignedStore

        return SignedStore(schema_version=1)

    def _load(self) -> None:
        import os

        from ..core.persistence import StateIntegrityError

        path = self._path()
        if not os.path.exists(path):
            return
        try:
            try:
                data = self._store().load(path)
            except StateIntegrityError:
                return
            if isinstance(data, dict):
                self.alerts = list(data.get("alerts", []))[-MAX_ALERTS:]
                self.adjustments = int(data.get("adjustments", 0))
        except Exception:
            pass

    def _persist(self) -> None:
        from ..core.persistence import atomic_write_json as _atomic

        data = {
            "alerts": self.alerts[-MAX_ALERTS:],
            "adjustments": self.adjustments,
            "updated": datetime.now().isoformat(),
        }
        try:
            self._store().save(self._path(), data)
        except Exception:
            try:
                _atomic(self._path(), data)
            except Exception:
                pass

    def rebuild_from_ledger(self, ledger=None) -> int:
        """Rebuild history signals from the signed ledger. Returns events replayed."""
        if ledger is None:
            try:
                from ..tracking.ledger import DecisionLedger

                ledger = DecisionLedger()
            except Exception:
                return 0
        try:
            ok, _ = ledger.verify_chain()
        except Exception:
            ok = False
        if not ok:
            return 0
        count = 0
        for payload in ledger.replay():
            try:
                conf = float(payload.get("confidence", 0.0))
            except (TypeError, ValueError):
                continue
            # Preserve consensus so restarted shields do not report false zero.
            try:
                consensus = payload.get("consensus_score")
                consensus = float(consensus) if consensus is not None else None
            except (TypeError, ValueError):
                consensus = None
            # Synthesize a minimal trace-like record for degradation stats.
            self.history.append(_LiteTrace(confidence=conf, consensus_score=consensus))  # type: ignore
            count += 1
        # Bound history.
        self.history = self.history[-500:]
        return count

    def check_quality(self, trace: TraceEntry) -> bool:
        self.history.append(trace)
        self.history = self.history[-500:]
        if trace.confidence.score < self.quality_threshold:
            alert = (
                f"Low confidence: {trace.confidence.score:.2f} "
                f"< {self.quality_threshold} "
                f"(query: {trace.query[:50]}...)"
            )
            self.alerts.append(alert)
            self.alerts = self.alerts[-MAX_ALERTS:]
            self._persist()
            return False
        if self._detect_degradation():
            alert = "Quality degradation detected in recent queries"
            self.alerts.append(alert)
            self.alerts = self.alerts[-MAX_ALERTS:]
            self._persist()
            return False
        return True

    def _score_of(self, item) -> float:
        try:
            if isinstance(item, TraceEntry):
                return float(item.confidence.score)
            return float(getattr(item.confidence, "score", getattr(item, "confidence", 0.0)))
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def _consensus_of(self, item) -> Optional[float]:
        try:
            conf = getattr(item, "confidence", None)
            return getattr(conf, "consensus_score", None)
        except AttributeError:
            return None

    def _detect_degradation(self) -> bool:
        if len(self.history) < 10:
            return False
        recent = self.history[-5:]
        previous = self.history[-10:-5]
        recent_avg = sum(self._score_of(t) for t in recent) / len(recent)
        previous_avg = sum(self._score_of(t) for t in previous) / len(previous)
        return (previous_avg - recent_avg) > 0.1

    def get_status(self) -> ShieldStatus:
        if not self.history:
            return ShieldStatus(
                active=True, quality_score=1.0, consensus_rate=1.0, alerts=[], adjustments_today=0
            )
        quality_score = sum(self._score_of(t) for t in self.history) / len(self.history)
        consensus_count = 0
        for t in self.history:
            if self._consensus_of(t) is not None:
                consensus_count += 1
        consensus_rate = consensus_count / len(self.history) if self.history else 1.0
        return ShieldStatus(
            active=True,
            quality_score=quality_score,
            consensus_rate=consensus_rate,
            alerts=self.alerts[-5:],
            adjustments_today=self.adjustments,
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
            recommendations.append("High alert count. Review routing configuration")
        return recommendations


class _LiteTrace:
    def __init__(self, confidence: float, consensus_score: Optional[float] = None):
        self.confidence = _LiteConf(confidence, consensus_score)
        self.query = ""


class _LiteConf:
    def __init__(self, score: float, consensus_score: Optional[float] = None):
        self.score = score
        self.consensus_score = consensus_score
