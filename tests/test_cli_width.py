"""CLI render width: capped, stable across terminal sizes, overridable.

Terminals re-wrap printed lines on resize, breaking box frames. All CLI
surfaces must render through get_console() at a capped width so widening
never disturbs output (only shrinking below the render width can, which no
printed-output program can avoid).
"""

import io
import re

from rich.console import Console

from modelhop.cli import output as out
from modelhop.cli.display import (
    DEFAULT_CONSOLE_WIDTH,
    PlainConsole,
    console_width,
    get_console,
)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _render(fn, *args, width):
    buf = io.StringIO()
    import modelhop.cli.output as out_mod

    old, out_mod.console = out_mod.console, Console(width=width, file=buf, force_terminal=True)
    try:
        fn(*args)
    finally:
        out_mod.console = old
    # Strip ANSI codes: zero-width in a real terminal, but counted by len().
    return [_ANSI.sub("", line) for line in buf.getvalue().splitlines()]


def test_width_capped_at_default(monkeypatch):
    monkeypatch.setenv("COLUMNS", "250")
    monkeypatch.delenv("MODELHOP_WIDTH", raising=False)
    assert console_width() == DEFAULT_CONSOLE_WIDTH == 100


def test_width_follows_narrow_terminal(monkeypatch):
    monkeypatch.setenv("COLUMNS", "70")
    monkeypatch.delenv("MODELHOP_WIDTH", raising=False)
    assert console_width() == 70


def test_width_override_and_bad_values(monkeypatch):
    monkeypatch.setenv("MODELHOP_WIDTH", "120")
    assert console_width() == 120
    assert get_console().width == 120
    monkeypatch.setenv("MODELHOP_WIDTH", "junk")
    monkeypatch.setenv("COLUMNS", "250")
    assert console_width() == 100
    monkeypatch.setenv("MODELHOP_WIDTH", "-5")
    assert console_width() == 100


def test_all_cli_consoles_capped():
    import modelhop.cli.commands.benchmark as b
    import modelhop.cli.commands.calibrate as cal
    import modelhop.cli.commands.cheat as ch
    import modelhop.cli.commands.config as cfg
    import modelhop.cli.commands.eval_cmd as ev
    import modelhop.cli.commands.example as ex
    import modelhop.cli.commands.history as hi
    import modelhop.cli.commands.hub_cmd as hub
    import modelhop.cli.commands.init as ini
    import modelhop.cli.commands.providers_cmd as prov
    import modelhop.cli.commands.route as rt
    import modelhop.cli.commands.serve_cmd as sv
    import modelhop.cli.commands.setup as su
    import modelhop.cli.commands.shield_cmd as sh
    import modelhop.cli.commands.stats as st
    import modelhop.cli.commands.welcome as wel
    import modelhop.cli.main as main

    modules = [main, out, b, cal, ch, cfg, ev, ex, hi, hub, ini, prov, rt, sv, su, sh, st, wel]
    assert len(modules) == 18
    for mod in modules:
        assert mod.console.width <= DEFAULT_CONSOLE_WIDTH, mod.__name__


def test_plain_detection(monkeypatch):
    import sys
    from types import SimpleNamespace

    from modelhop.cli.display import is_plain_output

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("MODELHOP_PLAIN", raising=False)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))
    assert is_plain_output() is False
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert is_plain_output() is True
    monkeypatch.setattr(sys, "stdout", SimpleNamespace())  # no isatty at all
    assert is_plain_output() is True
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setenv("NO_COLOR", "1")
    assert is_plain_output() is True
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("MODELHOP_PLAIN", "1")
    assert is_plain_output() is True


def test_get_console_plain_vs_tty(monkeypatch):
    import sys
    from types import SimpleNamespace

    from modelhop.cli.display import PlainConsole, get_console

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("MODELHOP_PLAIN", raising=False)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert isinstance(get_console(), PlainConsole)
    assert isinstance(get_console(force_terminal=True), PlainConsole)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: True))
    tty_console = get_console(force_terminal=True)
    assert type(tty_console) is Console
    assert tty_console.width <= DEFAULT_CONSOLE_WIDTH


def test_welcome_piped_is_plain_ascii():
    from click.testing import CliRunner

    import modelhop.cli.commands.welcome as wel
    from modelhop.cli.display import PlainConsole
    from modelhop.cli.main import cli

    buf = io.StringIO()
    old = wel.console
    wel.console = PlainConsole(width=80, file=buf)
    try:
        result = CliRunner().invoke(cli, ["welcome"])
    finally:
        wel.console = old
    assert result.exit_code == 0
    text = buf.getvalue()
    assert "Welcome to ModelHop!" in text
    assert ":frog:" not in text and "🐸" not in text
    assert "\x1b[" not in text  # no ANSI leaks into pipes
    assert "+" in text and "-" * 10 in text  # ASCII frames
    assert text.isascii()  # safe in any shell code page


def test_emoji_strip_only_known_codes():
    from modelhop.cli.display import PlainConsole

    buf = io.StringIO()
    c = PlainConsole(width=100, file=buf)
    c.print("meet at 12:30:45 see http://x :frog: done :not_a_code:")
    text = buf.getvalue()
    assert "12:30:45" in text and "http://x" in text
    assert ":frog:" not in text and "done" in text
    assert ":not_a_code:" in text  # unknown codes left alone


def test_distribution_ascii_in_plain_mode():
    import modelhop.cli.output as out_mod

    buf = io.StringIO()
    old = out_mod.console
    out_mod.console = PlainConsole(width=80, file=buf)
    try:
        out.print_distribution({"a": 80})
    finally:
        out_mod.console = old
    text = buf.getvalue()
    assert "#" in text and ":green_circle:" not in text


def test_every_helper_is_ascii_in_plain_mode(make_analysis, sample_models):
    """Every print_* helper (panels, table titles/headers, bars) must be
    pure ASCII through PlainConsole: no emoji, no ANSI, no box-drawing."""
    from types import SimpleNamespace

    import modelhop.cli.output as out_mod
    from modelhop.core.models import CostAnalysis, RoutingDecision

    cost = CostAnalysis(
        actual_cost=0.0,
        would_have_cost=10.0,
        savings=10.0,
        savings_percentage=95.0,
        model_used="m",
        tier="free",
    )
    bench = {
        "gpt4_cost": 1.0,
        "modelhop_cost": 0.1,
        "savings_pct": 90.0,
        "gpt4_avg": 0.1,
        "modelhop_avg": 0.01,
        "gpt4_latency": 2.0,
        "modelhop_latency": 1.0,
        "latency_improvement": 50.0,
        "gpt4_quality": 90.0,
        "modelhop_quality": 85.0,
        "quality_delta": 1.5,
    }
    buf = io.StringIO()
    old = out_mod.console
    out_mod.console = PlainConsole(width=100, file=buf)
    try:
        out.print_header()
        out.print_analysis(make_analysis())
        out.print_routing(
            RoutingDecision(model=sample_models[0], tier=sample_models[0].tier, reason="why")
        )
        out.print_response(SimpleNamespace(content="hello answer"))
        out.print_cost(cost)
        out.print_hop_time(100)
        out.print_benchmark_results(bench)
        out.print_distribution({"a": 80, "b": 20})
        out.print_hop_score(95)
    finally:
        out_mod.console = old
    text = buf.getvalue()
    assert text.isascii(), sorted({c for c in text if ord(c) > 127})
    assert "\x1b[" not in text
    assert "ModelHop" in text and "Benchmark" in text and "EXCELLENT" in text

    # User data is never mangled: non-ASCII response text passes through
    # untouched (only chrome is transliterated).
    buf2 = io.StringIO()
    out_mod.console = PlainConsole(width=100, file=buf2)
    try:
        out.print_response(SimpleNamespace(content="héllo wörld — café"))
    finally:
        out_mod.console = old
    assert "héllo wörld — café" in buf2.getvalue()


def test_welcome_percent_and_utf8_stdio():
    from click.testing import CliRunner

    from modelhop.cli.main import _ensure_utf8_stdio, cli

    _ensure_utf8_stdio()  # must never raise, even on replaced streams
    _ensure_utf8_stdio()  # idempotent
    result = CliRunner().invoke(cli, ["welcome"])
    assert result.exit_code == 0
    assert "60-90%" in result.output
    assert "60-90%%" not in result.output


def test_panels_fit_render_width(make_analysis, sample_models):
    from types import SimpleNamespace

    from modelhop.core.models import CostAnalysis, RoutingDecision

    cost = CostAnalysis(
        actual_cost=0.0,
        would_have_cost=10.0,
        savings=10.0,
        savings_percentage=95.0,
        model_used="m",
        tier="free",
    )
    for width in (80, 100):
        for lines in (
            _render(out.print_header, width=width),
            _render(out.print_response, SimpleNamespace(content="hello " * 50), width=width),
            _render(out.print_cost, cost, width=width),
            _render(out.print_hop_score, 95, width=width),
            _render(
                out.print_routing,
                RoutingDecision(model=sample_models[0], tier=sample_models[0].tier, reason="why"),
                width=width,
            ),
            _render(out.print_analysis, make_analysis(), width=width),
        ):
            assert lines, "expected rendered output"
            assert max(len(line) for line in lines) <= width
