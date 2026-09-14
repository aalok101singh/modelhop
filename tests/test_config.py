"""Tests for configuration loading."""
import pytest
import yaml
from pathlib import Path
from modelhop.config import EXAMPLE_CONFIG, Config


class TestExampleConfig:
    """Tests for EXAMPLE_CONFIG structure."""

    def test_has_models(self):
        assert "models" in EXAMPLE_CONFIG
        assert isinstance(EXAMPLE_CONFIG["models"], list)
        assert len(EXAMPLE_CONFIG["models"]) > 0

    def test_has_routing(self):
        assert "routing" in EXAMPLE_CONFIG
        assert "confidence_threshold" in EXAMPLE_CONFIG["routing"]

    def test_model_required_fields(self):
        required_fields = [
            "name", "provider", "model", "tier",
            "capabilities", "cost_per_1k_input", "cost_per_1k_output",
            "api_key_env",
        ]
        for model in EXAMPLE_CONFIG["models"]:
            for field in required_fields:
                assert field in model, f"Missing '{field}' in model '{model.get('name')}'"

    def test_yaml_serialization(self):
        yaml_str = yaml.dump(EXAMPLE_CONFIG, default_flow_style=False)
        assert "models:" in yaml_str
        loaded = yaml.safe_load(yaml_str)
        assert loaded == EXAMPLE_CONFIG


class TestConfig:
    """Tests for Config class."""

    def test_config_loads_with_no_file(self, tmp_path):
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(str(config_file))
        assert config.config == EXAMPLE_CONFIG

    def test_config_loads_from_yaml(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        test_data = {"models": [{"name": "test"}], "routing": {}}
        config_file.write_text(yaml.dump(test_data))

        config = Config(str(config_file))
        assert config.config["models"][0]["name"] == "test"

    def test_get_models(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(EXAMPLE_CONFIG))

        config = Config(str(config_file))
        models = config.get_models()
        assert len(models) == 3
        assert models[0].name == "groq-qwen3-8-27b"

    def test_get_routing_config(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(EXAMPLE_CONFIG))

        config = Config(str(config_file))
        routing = config.get_routing_config()
        assert "confidence_threshold" in routing
