import os
from typing import Dict, List, Optional

from ..config import Config
from ..core.models import ModelConfig, Tier
from .providers.base import BaseProvider
from .providers.gemini import GeminiProvider
from .providers.groq import GroqProvider
from .providers.openai import OpenAIProvider

PROVIDER_MAP: Dict[str, type] = {
    "groq": GroqProvider,
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}

try:
    from .providers.anthropic import AnthropicProvider

    PROVIDER_MAP["anthropic"] = AnthropicProvider
except ImportError:
    pass


class ModelRegistry:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._models = self.config.get_models()
        self._providers: Dict[str, BaseProvider] = {}
        self._init_providers()

    def _init_providers(self) -> None:
        for model in self._models:
            if model.name in self._providers:
                continue
            provider_cls = PROVIDER_MAP.get(model.provider)
            if provider_cls is None:
                continue
            api_key = os.getenv(model.api_key_env, "")
            if not api_key:
                continue
            try:
                provider = provider_cls(api_key=api_key, model=model.model)
                self._providers[model.name] = provider
            except Exception:
                continue

    def get_models(self) -> List[ModelConfig]:
        return self._models

    def get_model(self, name: str) -> Optional[ModelConfig]:
        for model in self._models:
            if model.name == name:
                return model
        return None

    def get_provider(self, model_name: str) -> Optional[BaseProvider]:
        return self._providers.get(model_name)

    def get_available_providers(self) -> Dict[str, BaseProvider]:
        return self._providers.copy()

    def get_models_by_tier(self, tier: Tier) -> List[ModelConfig]:
        return [m for m in self._models if m.tier == tier]

    def get_models_by_capability(self, capability: str) -> List[ModelConfig]:
        return [m for m in self._models if capability in m.capabilities]

    def get_cheapest_model(self, capabilities: Optional[List[str]] = None) -> Optional[ModelConfig]:
        candidates = self._models
        if capabilities:
            candidates = [m for m in candidates if all(c in m.capabilities for c in capabilities)]
        if not candidates:
            candidates = self._models
        tier_order = {Tier.FREE: 0, Tier.MID: 1, Tier.PREMIUM: 2}
        candidates.sort(
            key=lambda m: (tier_order.get(m.tier, 3), m.cost_per_1k_input + m.cost_per_1k_output)
        )
        return candidates[0] if candidates else None
