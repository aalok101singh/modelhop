"""Tests for provider construction and validation."""

from modelhop.config import Config
from modelhop.registry.model_registry import ModelRegistry


def test_model_registry_instantiates_only_keyed_providers(tmp_path):
    """Providers without API keys should not be instantiated."""
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: groq-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
  - name: openai-a
    provider: openai
    model: gpt-4
    tier: premium
    capabilities: [coding]
    cost_per_1k_input: 0.03
    cost_per_1k_output: 0.06
    api_key_env: OPENAI_API_KEY
routing:
  confidence_threshold: 0.7
  cross_model_consensus: true
  fallback: cascade
  max_retries: 3
""")
    # No keys in env -> no providers instantiated
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    providers = registry.get_available_providers()
    assert len(providers) == 0


def test_get_models_returns_all_configured(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: groq-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    models = registry.get_models()
    assert len(models) == 1
    assert models[0].name == "groq-a"


def test_get_model_by_name(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: groq-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    model = registry.get_model("groq-a")
    assert model is not None
    assert model.name == "groq-a"
    assert registry.get_model("nonexistent") is None


def test_get_models_preserves_config_order_and_cheapest_sorts(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: free-expensive
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0.01
    cost_per_1k_output: 0.01
    api_key_env: GROQ_API_KEY
  - name: free-cheap
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0.0
    cost_per_1k_output: 0.0
    api_key_env: GROQ_API_KEY
  - name: premium-a
    provider: openai
    model: gpt-4
    tier: premium
    capabilities: [coding]
    cost_per_1k_input: 0.03
    cost_per_1k_output: 0.06
    api_key_env: OPENAI_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    models = registry.get_models()
    # Config order preserved: free-expensive, free-cheap, premium-a
    assert models[0].name == "free-expensive"
    assert models[1].name == "free-cheap"
    assert models[2].name == "premium-a"
    # Cheapest lookup sorts by (tier, cost) -> free-cheap first
    cheapest = registry.get_cheapest_model(["general"])
    assert cheapest.name == "free-cheap"


def test_get_models_by_tier(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: free-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
  - name: premium-a
    provider: openai
    model: gpt-4
    tier: premium
    capabilities: [coding]
    cost_per_1k_input: 0.03
    cost_per_1k_output: 0.06
    api_key_env: OPENAI_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    free_models = registry.get_models_by_tier("free")
    premium_models = registry.get_models_by_tier("premium")
    assert len(free_models) == 1
    assert len(premium_models) == 1


def test_get_models_by_capability(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: free-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general, coding]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
  - name: premium-a
    provider: openai
    model: gpt-4
    tier: premium
    capabilities: [coding]
    cost_per_1k_input: 0.03
    cost_per_1k_output: 0.06
    api_key_env: OPENAI_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    coding_models = registry.get_models_by_capability("coding")
    assert len(coding_models) == 2
    for m in coding_models:
        assert "coding" in m.capabilities


def test_get_cheapest_model(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text("""
models:
  - name: free-a
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general]
    cost_per_1k_input: 0
    cost_per_1k_output: 0
    api_key_env: GROQ_API_KEY
  - name: premium-a
    provider: openai
    model: gpt-4
    tier: premium
    capabilities: [coding]
    cost_per_1k_input: 0.03
    cost_per_1k_output: 0.06
    api_key_env: OPENAI_API_KEY
routing: {}
""")
    cfg = Config(str(config_file))
    registry = ModelRegistry(cfg)
    cheapest = registry.get_cheapest_model()
    assert cheapest.name == "free-a"
    cheapest_coding = registry.get_cheapest_model(["coding"])
    assert cheapest_coding.name == "premium-a"
