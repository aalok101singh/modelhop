"""Tests for configuration loading."""
import pytest
import yaml
from pathlib import Path
from modelhop.config import EXAMPLE_CONFIG


class TestConfig:
    """Tests for configuration handling."""

    def test_example_config_structure(self):
        """Test that EXAMPLE_CONFIG has expected structure."""
        assert "models" in EXAMPLE_CONFIG
        assert isinstance(EXAMPLE_CONFIG["models"], list)
        assert len(EXAMPLE_CONFIG["models"]) > 0

    def test_model_config_fields(self):
        """Test that each model has required fields."""
        required_fields = [
            "name",
            "provider",
            "model",
            "tier",
            "capabilities",
            "cost_per_1k_input",
            "cost_per_1k_output",
            "api_key_env",
        ]
        for model in EXAMPLE_CONFIG["models"]:
            for field in required_fields:
                assert field in model, f"Missing field '{field}' in model '{model.get('name')}'"

    def test_config_yaml_serialization(self):
        """Test that config can be serialized to YAML."""
        yaml_str = yaml.dump(EXAMPLE_CONFIG, default_flow_style=False)
        assert isinstance(yaml_str, str)
        assert "models:" in yaml_str

    def test_config_yaml_deserialization(self, sample_config):
        """Test that config can be loaded from YAML."""
        yaml_str = yaml.dump(sample_config, default_flow_style=False)
        loaded = yaml.safe_load(yaml_str)
        assert loaded == sample_config
