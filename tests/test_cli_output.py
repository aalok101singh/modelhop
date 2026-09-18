"""cli/output.py formatting helpers: every branch, no exceptions."""

from types import SimpleNamespace

from modelhop.cli import output as out
from modelhop.core.models import CostAnalysis, EmotionalTone, QueryAnalysis, RoutingDecision


def _cost(pct):
    return CostAnalysis(
        actual_cost=0.0,
        would_have_cost=10.0,
        savings=10.0,
        savings_percentage=pct,
        model_used="m",
        tier="free",
    )


def test_print_header(capsys):
    out.print_header()
    assert "ModelHop" in capsys.readouterr().out


def test_print_analysis_neutral(make_analysis, capsys):
    out.print_analysis(make_analysis())
    assert "Analyzing" in capsys.readouterr().out


def test_print_analysis_tone(make_analysis, capsys):
    a = make_analysis()
    a = QueryAnalysis(
        complexity=a.complexity,
        level=a.level,
        capabilities_needed=["coding"],
        emotional_tone=EmotionalTone.FRUSTRATED,
    )
    out.print_analysis(a)
    assert "frustrated" in capsys.readouterr().out


def test_print_routing(sample_models, make_analysis, capsys):
    model = sample_models[0]
    out.print_routing(RoutingDecision(model=model, tier=model.tier, reason="why"))
    assert model.name in capsys.readouterr().out


def test_print_response(capsys):
    out.print_response(SimpleNamespace(content="hello answer"))
    assert "hello answer" in capsys.readouterr().out


def test_print_cost_badges(capsys):
    out.print_cost(_cost(95.0))
    assert "AMAZING" in capsys.readouterr().out
    out.print_cost(_cost(60.0))
    assert "GREAT" in capsys.readouterr().out
    out.print_cost(_cost(10.0))
    assert "Some savings" in capsys.readouterr().out


def test_print_hop_time_branches(capsys):
    out.print_hop_time(100)
    assert "Blazing fast" in capsys.readouterr().out
    out.print_hop_time(700)
    assert "Fast" in capsys.readouterr().out
    out.print_hop_time(1500)
    assert "Good" in capsys.readouterr().out


def _bench(quality=None, delta=None):
    return {
        "gpt4_cost": 1.0,
        "modelhop_cost": 0.1,
        "savings_pct": 90.0,
        "gpt4_avg": 0.1,
        "modelhop_avg": 0.01,
        "gpt4_latency": 2.0,
        "modelhop_latency": 1.0,
        "latency_improvement": 50.0,
        "gpt4_quality": quality,
        "modelhop_quality": 85.0,
        "quality_delta": delta,
    }


def test_print_benchmark_no_quality(capsys):
    out.print_benchmark_results(_bench())
    captured = capsys.readouterr().out
    assert "Benchmark" in captured
    assert "not measured" in captured


def test_print_benchmark_with_quality(capsys):
    out.print_benchmark_results(_bench(quality=90.0, delta=1.5))
    assert "Benchmark" in capsys.readouterr().out


def test_print_distribution(capsys):
    out.print_distribution({"a": 80, "b": 20})
    assert "a" in capsys.readouterr().out


def test_print_hop_score_branches(capsys):
    out.print_hop_score(95)
    assert "EXCELLENT" in capsys.readouterr().out
    out.print_hop_score(75)
    assert "GOOD" in capsys.readouterr().out
    out.print_hop_score(55)
    assert "AVERAGE" in capsys.readouterr().out
    out.print_hop_score(10)
    assert "NEEDS IMPROVEMENT" in capsys.readouterr().out
