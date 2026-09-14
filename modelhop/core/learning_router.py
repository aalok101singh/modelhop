from typing import List, Optional, Dict, Tuple
from collections import defaultdict
from .models import (
    QueryAnalysis, RoutingDecision, ModelConfig, QueryFeatures,
    QueryType, Tier, ComplexityLevel, Experience
)
from .memory import ExperienceMemory
from .performance import PerformanceTracker
from .features import FeatureExtractor

MIN_EXPERIENCES_FOR_LEARNING = 3
ESCALATION_QUALITY_THRESHOLD = 0.65
HIGH_CONFIDENCE_THRESHOLD = 0.75
CAPABILITY_ROUTING_THRESHOLD = 0.55


class LearningRouter:
    """Routes queries using experience memory, performance data, and signal analysis."""

    def __init__(
        self,
        models: List[ModelConfig],
        memory: ExperienceMemory,
        performance: PerformanceTracker,
    ):
        self.models = models
        self.memory = memory
        self.performance = performance
        self.feature_extractor = FeatureExtractor()
        self._model_map = {m.name: m for m in models}
        self._sort_models()

    def _sort_models(self):
        tier_order = {Tier.FREE: 0, Tier.MID: 1, Tier.PREMIUM: 2}
        self.models.sort(
            key=lambda m: (
                tier_order.get(m.tier, 3),
                m.cost_per_1k_input + m.cost_per_1k_output,
            )
        )

    def route(
        self,
        analysis: QueryAnalysis,
        query_features: Optional[QueryFeatures] = None,
    ) -> Tuple[RoutingDecision, str]:
        reasoning_parts = []

        enhanced_analysis = self._enhance_analysis(analysis, query_features, reasoning_parts)

        experience_decision = self._experience_based_route(
            enhanced_analysis, query_features, reasoning_parts
        )
        if experience_decision is not None:
            return experience_decision, " | ".join(reasoning_parts)

        capability_decision = self._capability_aware_route(
            enhanced_analysis, reasoning_parts
        )
        if capability_decision is not None:
            return capability_decision, " | ".join(reasoning_parts)

        decision = self._complexity_based_route(enhanced_analysis, reasoning_parts)
        return decision, " | ".join(reasoning_parts)

    def _enhance_analysis(
        self,
        analysis: QueryAnalysis,
        query_features: Optional[QueryFeatures],
        reasoning_parts: List[str],
    ) -> QueryAnalysis:
        if query_features is None:
            return analysis

        signal_complexity = self._compute_signal_complexity(query_features)
        signal_capabilities = self._compute_signal_capabilities(query_features)

        merged_complexity = analysis.complexity * 0.4 + signal_complexity * 0.6
        merged_complexity = max(0.0, min(1.0, merged_complexity))

        merged_capabilities = list(set(analysis.capabilities_needed) | signal_capabilities)

        if signal_complexity > analysis.complexity + 0.2:
            reasoning_parts.append(
                f"Signals boosted complexity from {analysis.complexity:.2f} to {merged_complexity:.2f}"
            )

        if signal_capabilities - set(analysis.capabilities_needed):
            new_caps = signal_capabilities - set(analysis.capabilities_needed)
            reasoning_parts.append(f"Signals detected additional capabilities: {', '.join(new_caps)}")

        return QueryAnalysis(
            complexity=merged_complexity,
            level=self._complexity_to_level(merged_complexity),
            capabilities_needed=merged_capabilities,
            emotional_tone=analysis.emotional_tone,
            estimated_tokens=analysis.estimated_tokens,
            reasoning=analysis.reasoning,
        )

    def _compute_signal_complexity(self, features: QueryFeatures) -> float:
        score = 0.15

        if features.code_keyword_count >= 3:
            score += 0.40
        elif features.code_keyword_count >= 2:
            score += 0.25
        elif features.code_keyword_count >= 1:
            score += 0.10

        if features.algorithm_term_count >= 2:
            score += 0.30
        elif features.algorithm_term_count >= 1:
            score += 0.15

        if features.has_constraints:
            score += 0.20
        if features.requires_optimization:
            score += 0.15
        if features.multi_step:
            score += 0.05
        if features.has_code_block:
            score += 0.10

        if features.is_implementation and features.code_keyword_count >= 2:
            score += 0.15

        if features.is_debugging:
            score += 0.10

        return min(1.0, score)

    def _compute_signal_capabilities(self, features: QueryFeatures) -> set:
        caps = set()
        if features.code_keyword_count >= 1 or features.is_implementation:
            caps.add("coding")
        if features.algorithm_term_count >= 1:
            caps.add("coding")
            caps.add("reasoning")
        if features.has_constraints or features.requires_optimization:
            caps.add("reasoning")
        if features.is_explanation:
            caps.add("technical")
        if features.is_creative:
            caps.add("creative")
        if features.is_debugging:
            caps.add("coding")
            caps.add("reasoning")
        if features.is_comparison:
            caps.add("reasoning")
            caps.add("technical")
        if not caps:
            caps.add("general")
        return caps

    def _complexity_to_level(self, complexity: float) -> ComplexityLevel:
        if complexity <= 0.3:
            return ComplexityLevel.SIMPLE
        elif complexity <= 0.6:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.COMPLEX

    def _experience_based_route(
        self,
        analysis: QueryAnalysis,
        query_features: Optional[QueryFeatures],
        reasoning_parts: List[str],
    ) -> Optional[RoutingDecision]:
        if query_features is None:
            return None

        similar = self.memory.find_similar(query_features, top_k=10, min_similarity=0.45)
        if len(similar) < MIN_EXPERIENCES_FOR_LEARNING:
            return None

        reasoning_parts.append(f"Found {len(similar)} similar past experiences")

        model_scores: Dict[str, List[float]] = defaultdict(list)
        model_fallback: Dict[str, int] = defaultdict(int)

        for exp in similar:
            model_scores[exp.model_name].append(exp.response_quality)
            if exp.fallback_used:
                model_fallback[exp.model_name] += 1

        ranked = []
        for model_name, scores in model_scores.items():
            avg_quality = sum(scores) / len(scores)
            sample_count = len(scores)
            fallback_count = model_fallback[model_name]
            fallback_rate = fallback_count / sample_count

            confidence = min(1.0, sample_count / 8)
            adjusted_quality = avg_quality * (1.0 - fallback_rate * 0.3)

            ranked.append({
                "model": model_name,
                "quality": avg_quality,
                "adjusted_quality": adjusted_quality,
                "samples": sample_count,
                "fallback_rate": fallback_rate,
                "confidence": confidence,
            })

        ranked.sort(key=lambda x: -x["adjusted_quality"])

        best = ranked[0]

        if best["confidence"] >= 0.4:
            reasoning_parts.append(
                f"Historical data: {best['model']} quality={best['quality']:.2f}, "
                f"fallback={best['fallback_rate']:.0%}, samples={best['samples']}"
            )

        if best["adjusted_quality"] < ESCALATION_QUALITY_THRESHOLD and best["confidence"] >= 0.4:
            reasoning_parts.append(
                f"Historical quality low ({best['adjusted_quality']:.2f}), escalating"
            )
            return self._escalate_to_premium(analysis, reasoning_parts)

        if analysis.complexity >= 0.65:
            models_tried = set(model_scores.keys())
            premium_available = [m for m in self.models if m.tier == Tier.PREMIUM]
            premium_tried = [m for m in premium_available if m.name in models_tried]

            if premium_available and not premium_tried:
                reasoning_parts.append(
                    f"Complex query ({analysis.complexity:.2f}) and premium not yet tried, "
                    f"routing to premium for quality comparison"
                )
                model = premium_available[0]
                alternatives = [
                    self._model_map[r["model"]]
                    for r in ranked[:2]
                    if r["model"] in self._model_map
                ]
                return RoutingDecision(
                    model=model,
                    tier=model.tier,
                    reason=f"Complex query: trying premium for quality comparison",
                    alternatives=alternatives,
                )

        if best["confidence"] >= 0.5 and best["adjusted_quality"] >= HIGH_CONFIDENCE_THRESHOLD:
            model = self._model_map.get(best["model"])
            if model:
                alternatives = [
                    self._model_map[r["model"]]
                    for r in ranked[1:3]
                    if r["model"] in self._model_map
                ]
                reasoning_parts.append(
                    f"Selected {model.name} based on historical performance"
                )
                return RoutingDecision(
                    model=model,
                    tier=model.tier,
                    reason=f"Historical performance: {best['quality']:.2f} quality, {best['fallback_rate']:.0%} fallback",
                    alternatives=alternatives,
                )

        return None

    def _capability_aware_route(
        self, analysis: QueryAnalysis, reasoning_parts: List[str]
    ) -> Optional[RoutingDecision]:
        required = set(analysis.capabilities_needed) - {"general"}
        premium_caps = {"coding", "creative", "analysis", "reasoning"}
        needs_advanced = bool(required & premium_caps)

        if not needs_advanced:
            return None

        capable_models = [
            m for m in self.models
            if all(c in m.capabilities for c in required)
        ]

        if not capable_models:
            capable_models = [
                m for m in self.models
                if any(c in m.capabilities for c in required & premium_caps)
            ]

        if not capable_models:
            return None

        premium_capable = [m for m in capable_models if m.tier == Tier.PREMIUM]

        if premium_capable and analysis.complexity >= CAPABILITY_ROUTING_THRESHOLD:
            model = premium_capable[0]
            alternatives = [m for m in capable_models if m.name != model.name][:2]
            reasoning_parts.append(
                f"Requires {', '.join(required & premium_caps)} -> premium tier"
            )
            return RoutingDecision(
                model=model,
                tier=model.tier,
                reason=f"Requires advanced capabilities: {', '.join(required & premium_caps)}",
                alternatives=alternatives,
            )

        return None

    def _complexity_based_route(
        self, analysis: QueryAnalysis, reasoning_parts: List[str]
    ) -> RoutingDecision:
        complexity = analysis.complexity

        if complexity <= 0.3:
            reasoning_parts.append(f"Simple query ({complexity:.2f}) -> free tier")
            free = [m for m in self.models if m.tier == Tier.FREE]
            if free:
                return RoutingDecision(
                    model=free[0],
                    tier=Tier.FREE,
                    reason=f"Simple query ({complexity:.2f}) -> free tier",
                    alternatives=free[1:3] if len(free) > 1 else [],
                )

        elif complexity <= 0.6:
            reasoning_parts.append(f"Medium query ({complexity:.2f}) -> free tier")
            free = [m for m in self.models if m.tier == Tier.FREE]
            if free:
                return RoutingDecision(
                    model=free[0],
                    tier=Tier.FREE,
                    reason=f"Medium complexity ({complexity:.2f}) -> free tier",
                    alternatives=[m for m in self.models if m.tier == Tier.MID][:2],
                )
            mid = [m for m in self.models if m.tier == Tier.MID]
            if mid:
                return RoutingDecision(
                    model=mid[0],
                    tier=Tier.MID,
                    reason=f"Medium complexity ({complexity:.2f}) -> mid tier",
                    alternatives=[],
                )

        else:
            if analysis.emotional_tone.value in ["neutral"]:
                free = [m for m in self.models if m.tier == Tier.FREE]
                if free:
                    reasoning_parts.append(
                        f"Complex query ({complexity:.2f}) but neutral tone -> trying free first"
                    )
                    return RoutingDecision(
                        model=free[0],
                        tier=Tier.FREE,
                        reason=f"Complex query ({complexity:.2f}) -> trying free first",
                        alternatives=[m for m in self.models if m.tier == Tier.PREMIUM][:2],
                    )

            premium = [m for m in self.models if m.tier == Tier.PREMIUM]
            if premium:
                reasoning_parts.append(f"Complex query ({complexity:.2f}) -> premium tier")
                return RoutingDecision(
                    model=premium[0],
                    tier=Tier.PREMIUM,
                    reason=f"Complex query ({complexity:.2f}) -> premium tier",
                    alternatives=[m for m in self.models if m.tier == Tier.MID][:2],
                )

        reasoning_parts.append("Fallback: using first available model")
        return RoutingDecision(
            model=self.models[0],
            tier=self.models[0].tier,
            reason="Fallback: using first available model",
            alternatives=self.models[1:3] if len(self.models) > 1 else [],
        )

    def _escalate_to_premium(
        self, analysis: QueryAnalysis, reasoning_parts: List[str]
    ) -> Optional[RoutingDecision]:
        premium = [m for m in self.models if m.tier == Tier.PREMIUM]
        if premium:
            fallback_prone = self.performance.get_fallback_prone_models()
            non_prone = [m for m in premium if m.name not in fallback_prone]
            if non_prone:
                model = non_prone[0]
            else:
                model = premium[0]

            alternatives = [m for m in premium if m.name != model.name][:2]
            reasoning_parts.append(f"Escalated to {model.name} (premium)")
            return RoutingDecision(
                model=model,
                tier=Tier.PREMIUM,
                reason="Escalated: historical quality is low for similar queries",
                alternatives=alternatives,
            )

        reasoning_parts.append("Escalation failed: no premium models available")
        return None
