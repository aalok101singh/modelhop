from typing import Optional, List
from .models import (
    ModelConfig, Tier, QueryAnalysis, RoutingDecision,
    ConfidenceResult
)


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
            if current_index + 1 < len(self.tier_order):
                return self.tier_order[current_index + 1]
        except ValueError:
            pass
        return None

    def get_models_for_tier(self, tier: Tier) -> List[ModelConfig]:
        return self.tier_models.get(tier, [])

    async def handle_failure(
        self,
        query: str,
        analysis: QueryAnalysis,
        failed_model: ModelConfig,
        error: Optional[str] = None
    ) -> Optional[RoutingDecision]:
        next_tier = self.get_next_tier(failed_model.tier)
        if next_tier is None:
            return None

        next_models = self.get_models_for_tier(next_tier)
        if not next_models:
            return None

        selected_model = next_models[0]
        return RoutingDecision(
            model=selected_model,
            tier=next_tier,
            reason=f"Fallback from {failed_model.name} ({failed_model.tier.value}) -> {selected_model.name} ({selected_model.tier.value})"
        )

    async def handle_low_confidence(
        self,
        query: str,
        analysis: QueryAnalysis,
        current_model: ModelConfig,
        confidence: ConfidenceResult
    ) -> Optional[RoutingDecision]:
        return await self.handle_failure(
            query, analysis, current_model,
            error=f"Low confidence: {confidence.score:.2f} < {confidence.threshold}"
        )
