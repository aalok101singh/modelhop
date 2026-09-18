"""CLI commands against a real ModelHop with injected fake providers.

Filesystem-isolated via tmp cwd. Covers cli/commands/route.py success paths
(rich/json/verbose/forced-model) plus stats/history/providers/hub/shield/eval.
"""

import json

import pytest
from click.testing import CliRunner

from modelhop import ModelHop
from modelhop.cache.semantic import SemanticCache
from modelhop.cli.main import cli
from modelhop.core.models import ProviderResponse


class FakeProvider:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt, max_tokens=2000, temperature=0.7, **kwargs):
        self.calls += 1
        return ProviderResponse(
            content="cli answer " * 60,
            model_used="fake",
            provider="fake",
            tokens_in=10,
            tokens_out=60,
            latency_ms=40,
        )


@pytest.fixture
def live_mh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    mh = ModelHop()
    mh.registry._providers = {m.name: FakeProvider() for m in mh.models}
    monkeypatch.setattr("modelhop.ModelHop", lambda *a, **k: mh)
    return mh


def test_route_no_keys_panel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    result = CliRunner().invoke(cli, ["route", "hello there"])
    assert result.exit_code == 0
    assert "No API keys" in result.output


def test_route_json(live_mh):
    result = CliRunner().invoke(cli, ["route", "hello world test query", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["model"] in {m.name for m in live_mh.models}
    assert payload["aux_calls"] == 0
    assert payload["cached"] is False
    assert "baseline_model" in payload


def test_route_rich(live_mh):
    result = CliRunner().invoke(cli, ["route", "hello world test query"])
    assert result.exit_code == 0, result.output
    assert "Cost Analysis" in result.output
    assert "Routed to" in result.output


def test_route_verbose(live_mh):
    result = CliRunner().invoke(cli, ["route", "hello world test query", "--verbose"])
    assert result.exit_code == 0, result.output
    assert "Routing Rationale" in result.output
    assert "System Intelligence" in result.output


def test_route_forced_model(live_mh):
    result = CliRunner().invoke(
        cli, ["route", "hello world test query", "-m", "groq-qwen3-8-27b", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["model"] == "groq-qwen3-8-27b"


def test_stats_empty_and_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["stats"])
    assert r.exit_code == 0
    assert "No queries routed yet" in r.output
    r = CliRunner().invoke(cli, ["stats", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["cost"]["query_count"] == 0


def test_history_empty_and_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["history"])
    assert r.exit_code == 0
    assert "No routing history" in r.output
    r = CliRunner().invoke(cli, ["history", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output) == []


def test_providers_no_keys_and_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["providers"])
    assert r.exit_code == 0
    assert "No API Key" in r.output
    r = CliRunner().invoke(cli, ["providers", "--json"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload and all(p["status"] == "no_key" for p in payload)


def test_hub_list_and_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["hub", "list"])
    assert r.exit_code == 0
    r = CliRunner().invoke(cli, ["hub", "list", "--json"])
    assert r.exit_code == 0
    assert isinstance(json.loads(r.output), list)
    dest = tmp_path / "dl.yaml"
    r = CliRunner().invoke(cli, ["hub", "download", "support-bot", "-d", str(dest)])
    assert r.exit_code == 0
    assert dest.exists()
    r = CliRunner().invoke(cli, ["hub", "download", "no-such-config"])
    assert r.exit_code == 0
    assert "not found" in r.output


def test_shield_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["shield"])
    assert r.exit_code == 0
    r = CliRunner().invoke(cli, ["shield", "status", "--json"])
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert "quality_score" in payload


def test_eval_offline_and_drift(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["eval", "offline", "--json"])
    assert r.exit_code == 0
    assert json.loads(r.output)["n"] == 0
    r = CliRunner().invoke(cli, ["eval", "drift", "--json"])
    assert r.exit_code == 0
    assert "status" in json.loads(r.output)
    r = CliRunner().invoke(cli, ["eval"])
    assert r.exit_code == 0


def test_calibrate_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(SemanticCache, "_try_load_embed", lambda self: None)
    r = CliRunner().invoke(cli, ["calibrate"])
    assert r.exit_code == 0
    assert "Not enough labeled outcomes" in r.output


def test_welcome_missing_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(cli, ["welcome"])
    assert r.exit_code == 0
