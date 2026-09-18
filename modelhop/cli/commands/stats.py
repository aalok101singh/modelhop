import json as json_mod
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table

from ..display import get_console

console = get_console()

#: Persisted counters cleared by `modelhop stats --reset`. Learning state
#: (bandit/memory) is deliberately NOT cleared.
RESET_FILES = [
    "cost_log.json",
    "trace_log.jsonl",
    "trace_log.json",
    "modelhop_ledger.jsonl",
    "modelhop_cache.sqlite",
    "modelhop_shield.json",
]


def reset_stats_files() -> list:
    removed = []
    for name in RESET_FILES:
        try:
            p = Path(name)
            if p.exists():
                p.unlink()
                removed.append(name)
        except OSError:
            pass
    return removed


@click.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--reset",
    is_flag=True,
    help="Clear lifetime counters (cost log, traces, ledger, cache, shield)",
)
def stats(json_output: bool, reset: bool) -> None:
    """:frog: Show routing statistics (lifetime totals)."""
    if reset:
        removed = reset_stats_files()
        if not json_output:
            console.print()
            detail = ", ".join(removed) if removed else "nothing to clear"
            console.print(
                Panel(
                    f"[bold green]:white_check_mark: Statistics reset.[/bold green]\n\n"
                    f"Cleared: [dim]{detail}[/dim]",
                    title=":frog: ModelHop Statistics",
                    border_style="green",
                    padding=(0, 1),
                )
            )
            console.print()
            return
        print(json_mod.dumps({"reset": True, "cleared": removed}))  # noqa: T201
        return

    from modelhop import ModelHop

    mh = ModelHop()
    cost_summary = mh.cost_tracker.get_summary()
    trace_stats = mh.trace_logger.get_stats()
    hop_stats = mh.hop_score.get_stats()

    if json_output:
        output = {
            "lifetime": True,
            "cost": cost_summary,
            "traces": trace_stats,
            "hop_score": hop_stats,
        }
        print(json_mod.dumps(output, indent=2))  # noqa: T201 - raw JSON, no rich wrap
    else:
        console.print()

        if cost_summary["query_count"] == 0:
            console.print(
                Panel(
                    "[yellow]No queries routed yet.[/yellow]\n\n"
                    'Run [cyan]modelhop route "your query"[/cyan] to get started!',
                    title=":frog: ModelHop Statistics (lifetime)",
                    border_style="cyan",
                )
            )
            console.print()
            return

        table = Table(
            title=":frog: ModelHop Statistics (lifetime)",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            padding=(0, 1),
            caption="[dim]Lifetime totals - run [cyan]modelhop stats --reset[/cyan] to clear[/dim]",
        )
        table.add_column("Metric", style="bold white", min_width=18)
        table.add_column("Value", style="green", min_width=16)

        table.add_row(":bar_chart: Total Queries", str(cost_summary["query_count"]))
        table.add_row(":moneybag: Total Cost", f"${cost_summary['total_cost']:.4f}")
        table.add_row(":sparkles: Total Savings", f"${cost_summary['total_savings']:.4f}")
        table.add_row(
            ":chart_with_upwards_trend: Savings %", f"{cost_summary['savings_percentage']:.1f}%"
        )
        table.add_row(":trophy: Hop Score", f"{hop_stats['score']}/100 ({hop_stats['rating']})")
        table.add_row(":brain: Avg Complexity", f"{trace_stats['avg_complexity']:.2f}")
        table.add_row(":mag: Avg Confidence", f"{trace_stats['avg_confidence']:.2f}")
        table.add_row(":zap: Avg Latency", f"{trace_stats['avg_latency_ms']:.0f}ms")
        table.add_row(
            ":arrows_counterclockwise: Fallback Rate", f"{trace_stats['fallback_rate']:.1f}%"
        )

        console.print(table)
        console.print()
