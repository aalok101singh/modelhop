import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from ..core.models import (
    TraceEntry, QueryAnalysis, RoutingDecision,
    ProviderResponse, ConfidenceResult, CostAnalysis, ModelConfig, Tier,
    ComplexityLevel, EmotionalTone
)


class TraceLogger:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path("trace_log.json")
        self.history: List[TraceEntry] = []
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r") as f:
                log = json.load(f)
            for entry in log.get("traces", []):
                trace = TraceEntry(
                    query_id=entry["query_id"],
                    query=entry["query"],
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                    analysis=QueryAnalysis(
                        complexity=entry["complexity"],
                        level=ComplexityLevel.SIMPLE if entry["complexity"] <= 0.3 else ComplexityLevel.MEDIUM if entry["complexity"] <= 0.6 else ComplexityLevel.COMPLEX,
                        capabilities_needed=["general"],
                        emotional_tone=EmotionalTone.NEUTRAL,
                    ),
                    decision=RoutingDecision(
                        model=ModelConfig(
                            name=entry["model"],
                            provider="",
                            model="",
                            tier=Tier(entry["tier"]),
                        ),
                        tier=Tier(entry["tier"]),
                        reason=""
                    ),
                    response=ProviderResponse(
                        content="",
                        model_used=entry["model"],
                        provider="",
                    ),
                    confidence=ConfidenceResult(
                        score=entry["confidence"],
                        is_confident=entry["confidence"] >= 0.7,
                        threshold=0.7,
                    ),
                    cost=CostAnalysis(
                        actual_cost=entry["actual_cost"],
                        would_have_cost=entry["actual_cost"] + entry["savings"],
                        savings=entry["savings"],
                        savings_percentage=0,
                        model_used=entry["model"],
                        tier=entry["tier"],
                    ),
                    fallback_used=entry.get("fallback_used", False),
                    total_latency_ms=entry.get("latency_ms", 0),
                )
                self.history.append(trace)
        except Exception:
            pass

    def log(
        self,
        query: str,
        analysis: QueryAnalysis,
        decision: RoutingDecision,
        response: ProviderResponse,
        confidence: ConfidenceResult,
        cost: CostAnalysis,
        fallback_used: bool = False,
        fallback_count: int = 0
    ) -> TraceEntry:
        trace = TraceEntry(
            query_id=str(uuid.uuid4())[:8],
            query=query,
            timestamp=datetime.now(),
            analysis=analysis,
            decision=decision,
            response=response,
            confidence=confidence,
            cost=cost,
            fallback_used=fallback_used,
            fallback_count=fallback_count,
            total_latency_ms=response.latency_ms
        )

        self.history.append(trace)
        self._save_trace(trace)
        return trace

    def _save_trace(self, trace: TraceEntry) -> None:
        try:
            if self.log_path.exists():
                with open(self.log_path, "r") as f:
                    log = json.load(f)
            else:
                log = {"traces": []}

            log["traces"].append({
                "query_id": trace.query_id,
                "query": trace.query,
                "timestamp": trace.timestamp.isoformat(),
                "complexity": trace.analysis.complexity,
                "model": trace.decision.model.name,
                "tier": trace.decision.tier.value,
                "confidence": trace.confidence.score,
                "actual_cost": trace.cost.actual_cost,
                "savings": trace.cost.savings,
                "latency_ms": trace.total_latency_ms,
                "fallback_used": trace.fallback_used
            })

            with open(self.log_path, "w") as f:
                json.dump(log, f, indent=2)
        except Exception:
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
                "fallback_rate": 0
            }

        return {
            "total_queries": len(self.history),
            "avg_complexity": sum(t.analysis.complexity for t in self.history) / len(self.history),
            "avg_confidence": sum(t.confidence.score for t in self.history) / len(self.history),
            "avg_latency_ms": sum(t.total_latency_ms for t in self.history) / len(self.history),
            "fallback_rate": sum(1 for t in self.history if t.fallback_used) / len(self.history) * 100
        }
