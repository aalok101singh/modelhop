"""C2 fixes: tokens, heuristic, hop-score predicate/rehydration, provider errors,
stats --reset, setup model wiring."""

import asyncio
import json

from modelhop.cli.provider_errors import (
    candidate_models,
    describe_provider_error,
)
from modelhop.core.confidence import ConfidenceEngine
from modelhop.core.models import CostAnalysis, ModelConfig, ProviderResponse, Tier
from modelhop.tracking.cost_tracker import estimate_cost
from modelhop.tracking.hop_score import HopScore, is_optimal_hop


def _resp(content, tokens_out=10):
    return ProviderResponse(
        content=content, model_used="m", provider="p", tokens_in=12, tokens_out=tokens_out
    )


def _model():
    return ModelConfig(
        name="groq-qwen",
        provider="groq",
        model="qwen/qwen3.8-27b",
        tier=Tier.FREE,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    )


# -- tokens ---------------------------------------------------------------
def test_cost_analysis_tokens_default_zero():
    c = CostAnalysis(
        actual_cost=0.0,
        would_have_cost=0.01,
        savings=0.01,
        savings_percentage=100.0,
        model_used="m",
        tier="free",
    )
    assert (c.tokens_in, c.tokens_out) == (0, 0)


def test_estimate_cost_carries_tokens():
    c = estimate_cost(_resp("x" * 60, tokens_out=25), _model())
    assert (c.tokens_in, c.tokens_out) == (12, 25)


# -- heuristic ------------------------------------------------------------
def test_greeting_is_confident_not_degraded():
    engine = ConfidenceEngine(threshold=0.7, fail_closed=True)
    result = asyncio.run(engine.check("hi", _resp("Hello! How can I help you today?")))
    assert result.is_confident is True
    assert result.degraded is False


def test_stub_still_below_threshold():
    engine = ConfidenceEngine(threshold=0.7, fail_closed=True)
    result = asyncio.run(engine.check("hi", _resp("Hi", tokens_out=2)))
    assert result.is_confident is False
    assert result.degraded is True


# -- hop predicate --------------------------------------------------------
def test_is_optimal_hop_matrix():
    assert is_optimal_hop(True, 0.01, 0.02) is True
    assert is_optimal_hop(True, 0.0, 0.02) is False
    assert is_optimal_hop(False, 0.01, 0.02) is False
    # No priced baseline (free-only config): confident counts.
    assert is_optimal_hop(True, 0.0, 0.0) is True
    assert is_optimal_hop(False, 0.0, 0.0) is False


def test_hopscore_rehydrates_jsonl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lines = [
        {
            "query_id": "a1",
            "confidence": {"score": 0.8, "threshold": 0.7},
            "cost": {"savings": 0.01, "would_have_cost": 0.02},
        },
        {
            "query_id": "a2",
            "confidence": {"score": 0.4, "threshold": 0.7},
            "cost": {"savings": 0.01, "would_have_cost": 0.02},
        },
    ]
    (tmp_path / "trace_log.jsonl").write_text(
        "\n".join(json.dumps(o) for o in lines) + "\n", encoding="utf-8"
    )
    h = HopScore()
    assert (h.total_queries, h.optimal_routes) == (2, 1)
    assert h.get_score() == 50


def test_hopscore_legacy_envelope_not_double_counted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "trace_log.json").write_text(
        json.dumps({"traces": [{"confidence": 0.9}, {"confidence": 0.1}]}),
        encoding="utf-8",
    )
    h = HopScore()
    assert (h.total_queries, h.optimal_routes) == (2, 1)


# -- provider errors ------------------------------------------------------
def test_describe_provider_error_kinds():
    class E401(Exception):
        pass

    e = E401("Error code: 401 - {'error': {'message': 'Incorrect API key'}}")
    assert describe_provider_error(e)[0] == "invalid_key"

    e = Exception(
        "Error code: 404 - {'error': {'code': 'model_not_found', "
        "'message': 'The model `gpt-4` does not exist'}}"
    )
    kind, msg = describe_provider_error(e, "openai", "gpt-4")
    assert kind == "model_not_found" and "gpt-4" in msg

    e = Exception(
        "Error code: 429 - {'error': {'code': 'credit_balance_exhausted', "
        "'message': 'You have no credits remaining'}}"
    )
    assert describe_provider_error(e, "openai")[0] == "no_credits"

    import asyncio as _aio

    assert describe_provider_error(_aio.TimeoutError())[0] == "network"
    assert describe_provider_error(Exception("boom"))[0] == "error"


def test_candidate_models_dedup_order():
    models = candidate_models("openai", "gpt-4")
    assert models[0] == "gpt-4"
    assert len(models) == len(set(models))
    assert "gpt-4o-mini" in models


# -- stats reset ----------------------------------------------------------
def test_reset_stats_files(tmp_path, monkeypatch):
    from modelhop.cli.commands.stats import RESET_FILES, reset_stats_files

    monkeypatch.chdir(tmp_path)
    (tmp_path / "cost_log.json").write_text("{}", encoding="utf-8")
    (tmp_path / "trace_log.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
    removed = reset_stats_files()
    assert "cost_log.json" in removed and "trace_log.jsonl" in removed
    assert set(RESET_FILES) >= {"cost_log.json", "trace_log.jsonl"}
    assert (tmp_path / "keep.txt").exists()
    assert not (tmp_path / "cost_log.json").exists()


def test_stats_reset_cli(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from modelhop.cli.main import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / "cost_log.json").write_text(
        json.dumps({"total_cost": 1, "total_savings": 2, "entries": []}), encoding="utf-8"
    )
    r = CliRunner().invoke(cli, ["stats", "--reset"])
    assert r.exit_code == 0
    assert not (tmp_path / "cost_log.json").exists()


# -- setup wiring ---------------------------------------------------------
def test_update_and_remove_config_models(tmp_path, monkeypatch):
    import yaml

    from modelhop.cli.commands import setup as su

    monkeypatch.chdir(tmp_path)
    (tmp_path / "modelhop.yaml").write_text(
        yaml.safe_dump(
            {
                "models": [
                    {
                        "name": "openai-gpt-4",
                        "provider": "openai",
                        "model": "gpt-4",
                        "tier": "premium",
                        "api_key_env": "OPENAI_API_KEY",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    su._update_config_models({"openai": "gpt-4o-mini"})
    cfg = yaml.safe_load((tmp_path / "modelhop.yaml").read_text(encoding="utf-8"))
    assert cfg["models"][0]["model"] == "gpt-4o-mini"
    assert "gpt-4o-mini" in cfg["models"][0]["name"]
    su._remove_config_models(["openai"])
    cfg = yaml.safe_load((tmp_path / "modelhop.yaml").read_text(encoding="utf-8"))
    assert cfg["models"] == []


def test_ensure_config_exists_creates_defaults(tmp_path, monkeypatch):
    import yaml

    from modelhop.cli.commands import setup as su

    monkeypatch.chdir(tmp_path)
    assert su._ensure_config_exists() is True
    cfg = yaml.safe_load((tmp_path / "modelhop.yaml").read_text(encoding="utf-8"))
    assert {m["provider"] for m in cfg["models"]} >= {"groq", "gemini", "openai"}
    # Second call leaves an existing file alone.
    assert su._ensure_config_exists() is False


def test_model_switch_wires_into_fresh_config(tmp_path, monkeypatch):
    import yaml

    from modelhop.cli.commands import setup as su

    monkeypatch.chdir(tmp_path)
    assert su._ensure_config_exists() is True
    su._update_config_models({"openai": "gpt-4o-mini"})
    cfg = yaml.safe_load((tmp_path / "modelhop.yaml").read_text(encoding="utf-8"))
    openai = [m for m in cfg["models"] if m["provider"] == "openai"]
    assert openai and openai[0]["model"] == "gpt-4o-mini"
