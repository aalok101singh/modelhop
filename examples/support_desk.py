"""
Example: support_desk — a customer-support bot powered by ModelHop.

Routes inbound support tickets through the cheapest capable model,
prints the answer alongside routing + cost details, then shows total
savings versus a GPT-4-only setup.

Run:
    python examples/support_desk.py
"""

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from modelhop import ModelHop, estimate_cost

console = Console()

TICKETS = [
    "How do I reset my password?",
    "Why is my inbox labeled as spam all of a sudden?",
    "Can I export my search history to a spreadsheet?",
    "My payments keep failing with a 'card declined' error but the bank says it's fine.",
    (
        "Design a zero-downtime migration plan to move 50TB of customer data from an "
        "on-premise Postgres cluster to a multi-region cloud deployment with strict "
        "compliance requirements and a two-week window."
    ),
]


async def main() -> None:
    mh = ModelHop()

    if not mh.registry.get_available_providers():
        console.print(
            Panel(
                "[bold red]No API keys found.[/bold red]\n\n"
                "Set at least one of GROQ_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY "
                "before running this example.",
                title=":warning: Configuration Error",
                border_style="red",
            )
        )
        return

    table = Table(title=":support: Support Desk — Routing Report", title_justify="left")
    table.add_column("Ticket")
    table.add_column("Model", style="cyan")
    table.add_column("Tier")
    table.add_column("Cost", justify="right")
    table.add_column("GPT-4 Would Cost", justify="right")
    table.add_column("Saved", justify="right")

    total_cost = 0.0
    total_would_have = 0.0

    for ticket in TICKETS:
        console.print(Panel(f"[bold]Ticket:[/bold] {ticket}", border_style="dim"))

        try:
            response = await mh.route(ticket)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/red]", title=":x: Route Failed", border_style="red"))
            console.print()
            continue

        model = mh.registry.get_model(response.model_used)
        if model is None:
            console.print()
            continue

        cost = estimate_cost(response, model)
        total_cost += cost.actual_cost
        total_would_have += cost.would_have_cost

        console.print(Panel(response.content, title=":bulb: Answer", border_style="cyan"))
        console.print(
            f"  :frog: {response.model_used}  ($ {cost.actual_cost:.4f} vs "
            f"$ {cost.would_have_cost:.4f} GPT-4, saved {cost.savings_percentage:.0f}%)"
        )
        console.print()

        tier_color = {"free": "green", "mid": "yellow", "premium": "red"}
        table.add_row(
            ticket[:60] + ("..." if len(ticket) > 60 else ""),
            response.model_used,
            f"[{tier_color.get(cost.tier, 'white')}]{cost.tier.upper()}[/]",
            f"${cost.actual_cost:.4f}",
            f"${cost.would_have_cost:.4f}",
            f"[green]${cost.savings:.4f}[/green]",
        )

    saved_pct = (
        (total_would_have - total_cost) / total_would_have * 100 if total_would_have > 0 else 0
    )
    table.add_row(
        "[bold]TOTALS[/bold]",
        "",
        "",
        f"[bold]${total_cost:.4f}[/bold]",
        f"[bold]${total_would_have:.4f}[/bold]",
        f"[bold green]${total_would_have - total_cost:.4f} ({saved_pct:.0f}%)[/bold green]",
        end_section=True,
    )
    console.print(table)
    console.print()

    hop = mh.hop_score.get_stats()
    console.print(
        f"  :frog: [bold]Hop Score:[/bold] {hop['score']}/100 ({hop['rating']})\n"
        f"  Total experiences: {mh.memory.get_overall_stats()['total']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
