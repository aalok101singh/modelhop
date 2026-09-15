"""Tests for community Hub."""

import tempfile
from pathlib import Path

import pytest
import yaml

from modelhop.hub.hub import Hub


@pytest.fixture
def hub_dir():
    with tempfile.TemporaryDirectory() as tmp:
        # Write three community configs
        for name, desc in [
            ("support-bot", "Support bot"),
            ("code-review", "Code review"),
            ("creative-writing", "Creative writing"),
        ]:
            cfg = {
                "version": "1.0",
                "name": name,
                "description": desc,
                "models": [
                    {
                        "name": "groq-a",
                        "provider": "groq",
                        "model": "qwen/qwen3.8-27b",
                        "tier": "free",
                        "capabilities": ["general"],
                        "cost_per_1k_input": 0,
                        "cost_per_1k_output": 0,
                        "api_key_env": "GROQ_API_KEY",
                    }
                ],
            }
            Path(tmp) / f"{name}.yaml"
            with open(Path(tmp) / f"{name}.yaml", "w") as f:
                yaml.dump(cfg, f)
        yield Path(tmp)


@pytest.fixture
def hub(hub_dir):
    return Hub()


def test_list_configs_finds_community_configs(hub):
    configs = hub.list_configs()
    assert len(configs) == 3
    names = {c.name for c in configs}
    assert names == {"support-bot", "code-review", "creative-writing"}


def test_get_config_by_name(hub):
    config = hub.get_config("support-bot")
    assert config is not None
    assert config.name == "support-bot"
    assert hub.get_config("nonexistent") is None


def test_download_writes_yaml(hub, tmp_path):
    dest = tmp_path / "downloaded.yaml"
    assert hub.download_config("support-bot", str(dest)) is True
    assert dest.exists()
    data = yaml.safe_load(dest.read_text())
    assert data["name"] == "support-bot"


def test_search_configs_by_tag(hub):
    # Tags not set in fixture, so search by name
    results = hub.search_configs("support")
    assert len(results) == 1
    assert results[0].name == "support-bot"
