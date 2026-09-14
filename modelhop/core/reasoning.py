from typing import List, Optional

from .memory import ExperienceMemory
from .models import QueryAnalysis, QueryFeatures, QueryType, RoutingDecision
from .performance import PerformanceTracker


class ReasoningEngine:
    """Generates natural language explanations for routing decisions."""

    def __init__(self, memory: ExperienceMemory, performance: PerformanceTracker):
        self.memory = memory
        self.performance = performance

    def explain(
        self,
        query: str,
        analysis: QueryAnalysis,
        decision: RoutingDecision,
        query_features: Optional[QueryFeatures] = None,
        merged_reasoning: str = "",
    ) -> str:
        parts = []

        self._explain_analysis(analysis, parts)
        self._explain_signals(query_features, parts)
        self._explain_memory(query_features, parts)
        self._explain_performance(decision, analysis, parts)
        self._explain_decision(decision, parts)
        self._explain_alternatives(decision, parts)

        if merged_reasoning:
            parts.insert(0, f"[Engine] {merged_reasoning}")

        return " | ".join(parts) if parts else f"Routed to {decision.model.name}"

    def _explain_analysis(self, analysis: QueryAnalysis, parts: List[str]):
        level_desc = {
            "simple": "Simple",
            "medium": "Medium",
            "complex": "Complex",
        }
        level = level_desc.get(analysis.level.value, "Unknown")
        parts.append(f"{level} query (complexity {analysis.complexity:.2f})")

        if analysis.capabilities_needed:
            caps = [c for c in analysis.capabilities_needed if c != "general"]
            if caps:
                parts.append(f"Requires: {', '.join(caps)}")

    def _explain_signals(self, features: Optional[QueryFeatures], parts: List[str]):
        if features is None:
            return

        signals = []
        if features.code_keyword_count >= 2:
            signals.append(f"{features.code_keyword_count} code keywords")
        if features.algorithm_term_count >= 1:
            signals.append(f"{features.algorithm_term_count} algorithm terms")
        if features.has_constraints:
            signals.append("has complexity constraints")
        if features.requires_optimization:
            signals.append("requires optimization")
        if features.is_implementation:
            signals.append("implementation intent")
        if features.is_debugging:
            signals.append("debugging intent")

        if signals:
            parts.append(f"Signals: {', '.join(signals)}")

    def _explain_memory(self, features: Optional[QueryFeatures], parts: List[str]):
        if features is None:
            return

        similar = self.memory.find_similar(features, top_k=5, min_similarity=0.45)
        if not similar:
            parts.append("No similar past experiences")
            return

        avg_quality = sum(e.response_quality for e in similar) / len(similar)
        fallback_count = sum(1 for e in similar if e.fallback_used)

        parts.append(
            f"Memory: {len(similar)} similar queries, "
            f"avg quality={avg_quality:.2f}, "
            f"fallbacks={fallback_count}"
        )

        model_qualities = {}
        for exp in similar:
            if exp.model_name not in model_qualities:
                model_qualities[exp.model_name] = []
            model_qualities[exp.model_name].append(exp.response_quality)

        if model_qualities:
            best_model = max(
                model_qualities, key=lambda m: sum(model_qualities[m]) / len(model_qualities[m])
            )
            best_avg = sum(model_qualities[best_model]) / len(model_qualities[best_model])
            parts.append(f"Best historical: {best_model} ({best_avg:.2f})")

    def _explain_performance(
        self, decision: RoutingDecision, analysis: QueryAnalysis, parts: List[str]
    ):
        query_type = self._infer_query_type(analysis)
        metrics = self.performance.get_metrics(decision.model.name, query_type)

        if metrics and metrics.sample_count >= 3:
            parts.append(
                f"Performance: {decision.model.name} on {query_type.value} = "
                f"{metrics.avg_quality:.2f} quality, "
                f"{metrics.fallback_rate:.0%} fallback, "
                f"{metrics.sample_count} samples"
            )

    def _explain_decision(self, decision: RoutingDecision, parts: List[str]):
        tier_emoji = {"free": "FREE", "mid": "MID", "premium": "PREMIUM"}
        tier = tier_emoji.get(decision.tier.value, decision.tier.value.upper())
        parts.append(f"Selected: {decision.model.name} [{tier}]")

    def _explain_alternatives(self, decision: RoutingDecision, parts: List[str]):
        if decision.alternatives:
            alt_names = [f"{m.name} ({m.tier.value})" for m in decision.alternatives]
            parts.append(f"Alternatives: {', '.join(alt_names)}")

    def _infer_query_type(self, analysis: QueryAnalysis) -> QueryType:
        caps = set(analysis.capabilities_needed)
        if "coding" in caps:
            return QueryType.IMPLEMENTATION
        if "creative" in caps:
            return QueryType.CREATIVE
        if "technical" in caps:
            return QueryType.EXPLANATION
        if analysis.complexity >= 0.7:
            return QueryType.IMPLEMENTATION
        return QueryType.GENERAL

    def explain_short(self, decision: RoutingDecision) -> str:
        tier_emoji = {"free": "FREE", "mid": "MID", "premium": "PREMIUM"}
        tier = tier_emoji.get(decision.tier.value, decision.tier.value.upper())
        return f"{decision.model.name} [{tier}]"
