from typing import List, Optional

from .models import ConfidenceResult, ModelConfig, QueryAnalysis, RoutingDecision, Tier


class CascadeFallback:
    def __init__(self, models: List[ModelConfig], max_retries: int = 3):
        self.models = models
        self.max_retries = max_retries
        self.tier_models = {
            Tier.FREE: [m for m in models if m.tier == Tier.FREE],
            Tier.MID: [m for m in models if m.tier == Tier.MID],
            Tier.PREMIUM: [m for m in models if m.tier == Tier.PREMIUM],
        }
        self.tier_order = [Tier.FREE, Tier.MID, Tier.PREMIUM]

    def get_next_tier(self, current_tier: Tier) -> Optional[Tier]:
        try:
            current_index = self.tier_order.index(current_tier)
        except ValueError:
            return None
        for tier in self.tier_order[current_index + 1 :]:
            if self.tier_models.get(tier):
                return tier
        return None

    def get_models_for_tier(self, tier: Tier) -> List[ModelConfig]:
        return self.tier_models.get(tier, [])

    def next_candidate(
        self,
        current: ModelConfig,
        analysis: Optional[QueryAnalysis] = None,
        tried: Optional[set] = None,
        available: Optional[set] = None,
    ) -> Optional[ModelConfig]:
        required = set(analysis.capabilities_needed) - {"general"} if analysis else set()
        tried = tried or set()
        available = available or set()
        try:
            current_index = self.tier_order.index(current.tier)
        except ValueError:
            current_index = -1

        for tier in self.tier_order[current_index + 1 :]:
            candidates = [
                m
                for m in self.tier_models.get(tier, [])
                if m.name not in tried
                and (not available or m.name in available)
                and (not required or required & set(m.capabilities))
            ]
            candidates.sort(key=lambda m: (m.cost_per_1k_input + m.cost_per_1k_output, m.name))
            if candidates:
                return candidates[0]
        return None

    async def handle_failure(
        self,
        query: str,
        analysis: QueryAnalysis,
        failed_model: ModelConfig,
        error: Optional[str] = None,
    ) -> Optional[RoutingDecision]:
        selected_model = self.next_candidate(
            failed_model, analysis, tried={failed_model.name}, available=None
        )
        if selected_model is None:
            return None

        return RoutingDecision(
            model=selected_model,
            tier=selected_model.tier,
            reason=f"Fallback from {failed_model.name} ({failed_model.tier.value}) -> {selected_model.name} ({selected_model.tier.value})",
        )

    async def handle_low_confidence(
        self,
        query: str,
        analysis: QueryAnalysis,
        current_model: ModelConfig,
        confidence: ConfidenceResult,
    ) -> Optional[RoutingDecision]:
        return await self.handle_failure(
            query,
            analysis,
            current_model,
            error=f"Low confidence: {confidence.score:.2f} < {confidence.threshold}",
        )
