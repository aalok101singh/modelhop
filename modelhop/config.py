import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .core.models import ModelConfig, Tier

DEFAULT_CONFIG_PATH = Path("modelhop.yaml")
ENV_PATH = Path(".env")


def _load_env_file() -> None:
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


_load_env_file()

EXAMPLE_CONFIG = {
    "version": "1.0",
    "name": "default",
    "models": [
        {
            "name": "groq-qwen3-8-27b",
            "provider": "groq",
            "model": "qwen/qwen3.8-27b",
            "tier": "free",
            "capabilities": ["faq", "general", "classification", "reasoning", "coding"],
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "api_key_env": "GROQ_API_KEY",
        },
        {
            "name": "gemini-3.6-flash",
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "tier": "free",
            "capabilities": ["faq", "general", "reasoning"],
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "api_key_env": "GEMINI_API_KEY",
        },
        {
            "name": "openai-gpt-4",
            "provider": "openai",
            "model": "gpt-4",
            "tier": "premium",
            "capabilities": ["reasoning", "coding", "analysis", "creative"],
            "cost_per_1k_input": 0.03,
            "cost_per_1k_output": 0.06,
            "api_key_env": "OPENAI_API_KEY",
        },
    ],
    "routing": {
        "confidence_threshold": 0.7,
        "cross_model_consensus": True,
        "fallback": "cascade",
        "max_retries": 3,
    },
    "shield": {"enabled": True, "quality_threshold": 0.8},
    "tracking": {"log_queries": True, "log_costs": True},
}


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        return EXAMPLE_CONFIG.copy()

    def save(self) -> None:
        with open(self.config_path, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False)

    def get_models(self) -> List[ModelConfig]:
        models = []
        for model_data in self.config.get("models", []):
            api_key_env = model_data.get("api_key_env", "")
            os.getenv(api_key_env, "")
            models.append(
                ModelConfig(
                    name=model_data["name"],
                    provider=model_data["provider"],
                    model=model_data["model"],
                    tier=Tier(model_data["tier"]),
                    capabilities=model_data.get("capabilities", []),
                    cost_per_1k_input=model_data.get("cost_per_1k_input", 0.0),
                    cost_per_1k_output=model_data.get("cost_per_1k_output", 0.0),
                    api_key_env=api_key_env,
                )
            )
        return models

    def get_routing_config(self) -> Dict[str, Any]:
        return self.config.get("routing", {})

    def get_shield_config(self) -> Dict[str, Any]:
        return self.config.get("shield", {})

    def get_tracking_config(self) -> Dict[str, Any]:
        return self.config.get("tracking", {})

    @staticmethod
    def create_default() -> "Config":
        config = Config()
        config.config = EXAMPLE_CONFIG.copy()
        config.save()
        return config
