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
    try:
        with open(ENV_PATH, "r", encoding="utf-8-sig") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                # Handle `export KEY=...` prefix.
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip inline comments that are outside quotes.
                # Simple scan: track single/double quote state.
                cleaned: list[str] = []
                in_single = False
                in_double = False
                for ch in value:
                    if ch == "'" and not in_double:
                        in_single = not in_single
                        cleaned.append(ch)
                        continue
                    if ch == '"' and not in_single:
                        in_double = not in_double
                        cleaned.append(ch)
                        continue
                    if ch == "#" and not in_single and not in_double:
                        break
                    cleaned.append(ch)
                value = "".join(cleaned).strip()
                # Strip one layer of matching quotes.
                if len(value) >= 2 and (
                    (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
                ):
                    value = value[1:-1]
                # Never eval; keep as literal string.
                if key and key not in os.environ:
                    # Basic key validation to avoid control-channel injection.
                    if key.replace("_", "").isalnum() and not key[0].isdigit():
                        os.environ[key] = value
    except OSError:
        return


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
        "cross_model_consensus": False,
        "llm_analysis": False,
        "fail_closed": True,
        "fallback": "cascade",
        "max_retries": 3,
        "decompose_queries": True,
        "trust_policy": {},
        "cost_savings_reference": "max",
        "policy_version": "1",
    },
    "shield": {"enabled": True, "quality_threshold": 0.8},
    "tracking": {"log_queries": True, "log_costs": True},
}


class Config:
    def __init__(self, config_path: Optional[str] = None):
        _load_env_file()
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
        from .core.models import TrustProfile

        models = []
        for model_data in self.config.get("models", []):
            api_key_env = model_data.get("api_key_env", "")
            trust_data = model_data.get("trust", {})
            try:
                trust = (
                    TrustProfile(**trust_data) if isinstance(trust_data, dict) else TrustProfile()
                )
            except Exception:
                trust = TrustProfile()
            models.append(
                ModelConfig(
                    name=model_data["name"],
                    provider=model_data["provider"],
                    model=model_data["model"],
                    tier=Tier(model_data["tier"]),
                    capabilities=model_data.get("capabilities", []),
                    cost_per_1k_input=model_data.get("cost_per_1k_input", 0.0),
                    cost_per_1k_output=model_data.get("cost_per_1k_output", 0.0),
                    max_tokens=model_data.get("max_tokens", 4096),
                    avg_latency_ms=model_data.get("avg_latency_ms", 500),
                    api_key_env=api_key_env,
                    trust=trust,
                    context_window=model_data.get("context_window", 0),
                    supports_tools=bool(model_data.get("supports_tools", False)),
                    supports_streaming=bool(model_data.get("supports_streaming", True)),
                    timeout_s=float(model_data.get("timeout_s", 30.0)),
                    max_retries=int(model_data.get("max_retries", 2)),
                    price_effective_date=model_data.get("price_effective_date"),
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
