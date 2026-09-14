import json as json_mod

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.command()
@click.option("--limit", "-l", default=20, help="Number of entries to show")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def history(limit: int, json_output: bool) -> None:
    """:frog: Show recent routing history."""
    from modelhop import ModelHop

    mh = ModelHop()
    entries = mh.trace_logger.get_history(limit=limit)

    if json_output:
        output = []
        for entry in entries:
            output.append(
                {
                    "query_id": entry.query_id,
                    "query": entry.query,
                    "model": entry.decision.model.name,
                    "tier": entry.decision.tier.value,
                    "confidence": entry.confidence.score,
                    "cost": entry.cost.actual_cost,
                    "savings": entry.cost.savings,
                    "latency_ms": entry.total_latency_ms,
                    "fallback_used": entry.fallback_used,
                }
            )
        console.print(json_mod.dumps(output, indent=2))
    else:
        if not entries:
            console.print()
            console.print(
                Panel(
                    "[yellow]No routing history yet.[/yellow]\n\n"
                    'Run [cyan]modelhop route "your query"[/cyan] to get started!',
                    title=":frog: Routing History",
                    border_style="cyan",
                )
            )
            console.print()
            return

        table = Table(
            title=f":frog: Routing History (last {len(entries)} entries)",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("ID", style="dim", min_width=10)
        table.add_column("Query", max_width=30, min_width=20)
        table.add_column("Model", style="green", min_width=18)
        table.add_column("Tier", min_width=8)
        table.add_column("Confidence", min_width=10)
        table.add_column("Cost", min_width=10)
        table.add_column("Latency", min_width=10)

        for entry in entries:
            tier_colors = {"free": "green", "mid": "yellow", "premium": "red"}
            color = tier_colors.get(entry.decision.tier.value, "white")
            table.add_row(
                entry.query_id,
                entry.query[:30] + "..." if len(entry.query) > 30 else entry.query,
                entry.decision.model.name,
                f"[{color}]{entry.decision.tier.value}[/{color}]",
                f"{entry.confidence.score:.2f}",
                f"${entry.cost.actual_cost:.4f}",
                f"{entry.total_latency_ms}ms",
            )

        console.print()
        console.print(table)
        console.print()
