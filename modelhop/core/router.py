from typing import List

from .models import ModelConfig, QueryAnalysis, RoutingDecision, Tier

PREMIUM_CAPABILITIES = {"coding", "creative", "analysis", "reasoning"}


class Router:
    def __init__(self, models: List[ModelConfig]):
        self.models = models
        self._sort_models()

    def _sort_models(self) -> None:
        tier_order = {Tier.FREE: 0, Tier.MID: 1, Tier.PREMIUM: 2}
        self.models.sort(
            key=lambda m: (
                tier_order.get(m.tier, 3),
                m.cost_per_1k_input + m.cost_per_1k_output
            )
        )

    def route(self, analysis: QueryAnalysis) -> RoutingDecision:
        capable_models = [
            m for m in self.models
            if self._has_capabilities(m, analysis.capabilities_needed)
        ]

        needs_premium = self._needs_premium_model(analysis)

        if needs_premium and capable_models:
            premium_capable = [m for m in capable_models if m.tier == Tier.PREMIUM]
            if premium_capable:
                selected = premium_capable[0]
                alternatives = [m for m in capable_models if m.name != selected.name][:2]
                reason = self._build_reason(analysis, selected)
                return RoutingDecision(
                    model=selected,
                    tier=selected.tier,
                    reason=reason,
                    alternatives=alternatives
                )

        if not capable_models:
            capable_models = self.models

        selected = self._select_by_complexity(analysis, capable_models)
        alternatives = [m for m in capable_models if m.name != selected.name][:2]
        reason = self._build_reason(analysis, selected)

        return RoutingDecision(
            model=selected,
            tier=selected.tier,
            reason=reason,
            alternatives=alternatives
        )

    def _needs_premium_model(self, analysis: QueryAnalysis) -> bool:
        required_premium = set(analysis.capabilities_needed) & PREMIUM_CAPABILITIES
        if required_premium:
            return True
        if analysis.complexity >= 0.7:
            return True
        return False

    def route_with_model(self, model_name: str, analysis: QueryAnalysis) -> RoutingDecision:
        model = next((m for m in self.models if m.name == model_name), None)
        if model is None:
            raise ValueError(f"Model '{model_name}' not found in registry")
        alternatives = [m for m in self.models if m.name != model_name][:2]
        return RoutingDecision(
            model=model,
            tier=model.tier,
            reason=f"Forced model selection: {model_name}",
            alternatives=alternatives
        )

    def _has_capabilities(self, model: ModelConfig, required: List[str]) -> bool:
        if not required:
            return True
        return all(cap in model.capabilities for cap in required)

    def _select_by_complexity(
        self,
        analysis: QueryAnalysis,
        capable_models: List[ModelConfig]
    ) -> ModelConfig:
        complexity = analysis.complexity

        if complexity <= 0.3:
            free_models = [m for m in capable_models if m.tier == Tier.FREE]
            if free_models:
                return free_models[0]

        elif complexity <= 0.6:
            free_models = [m for m in capable_models if m.tier == Tier.FREE]
            if free_models:
                return free_models[0]
            mid_models = [m for m in capable_models if m.tier == Tier.MID]
            if mid_models:
                return mid_models[0]

        else:
            free_models = [m for m in capable_models if m.tier == Tier.FREE]
            if free_models and analysis.emotional_tone.value in ["neutral"]:
                return free_models[0]
            premium_models = [m for m in capable_models if m.tier == Tier.PREMIUM]
            if premium_models:
                return premium_models[0]

        return capable_models[0]

    def escalate_to_premium(self, analysis: QueryAnalysis) -> RoutingDecision:
        premium_models = [m for m in self.models if m.tier == Tier.PREMIUM]
        if premium_models:
            selected = premium_models[0]
            alternatives = [m for m in self.models if m.name != selected.name][:2]
            return RoutingDecision(
                model=selected,
                tier=Tier.PREMIUM,
                reason="Escalated to premium: historical quality is low for similar queries",
                alternatives=alternatives,
            )
        return self.route(analysis)

    def _build_reason(self, analysis: QueryAnalysis, model: ModelConfig) -> str:
        required_premium = set(analysis.capabilities_needed) & PREMIUM_CAPABILITIES
        if required_premium:
            return f"Requires {', '.join(required_premium)} -> {model.tier.value} tier"
        if analysis.complexity <= 0.3:
            return f"Simple query ({analysis.complexity:.2f}) -> {model.tier.value} tier"
        elif analysis.complexity <= 0.6:
            return f"Medium complexity ({analysis.complexity:.2f}) -> {model.tier.value} tier"
        else:
            return f"Complex query ({analysis.complexity:.2f}) -> {model.tier.value} tier"
