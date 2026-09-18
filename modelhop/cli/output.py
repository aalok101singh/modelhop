from rich.panel import Panel
from rich.table import Table

from .._version import get_version
from .display import get_console, is_plain_output, tier_color, tier_emoji

console = get_console()


def print_header() -> None:
    console.print()
    console.print(
        Panel(
            f"[bold green]:frog: ModelHop v{get_version()}[/bold green]\n"
            "[dim]Save 60-90% on LLM costs by hopping to the right model[/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )
    console.print()


def print_analysis(analysis) -> None:
    console.print("  :brain: [bold]Analyzing...[/bold]")
    console.print(
        f"     Complexity : [cyan]{analysis.complexity:.2f}[/cyan] ({analysis.level.value})"
    )
    console.print(f"     Capabilities : {', '.join(analysis.capabilities_needed)}")
    if analysis.emotional_tone.value != "neutral":
        console.print(f"     Tone : [yellow]{analysis.emotional_tone.value}[/yellow]")
    console.print()


def print_routing(decision) -> None:
    color = tier_color(decision.tier.value)
    emoji = tier_emoji(decision.tier.value)
    console.print("  :dart: [bold]Routing...[/bold]")
    console.print(f"     Model : [bold green]{decision.model.name}[/bold green]")
    console.print(f"     Tier  : [{color}]{emoji} {decision.tier.value.upper()}[/{color}]")
    console.print(f"     Reason: [dim]{decision.reason}[/dim]")
    console.print()


def print_response(response) -> None:
    console.print(
        Panel(
            response.content,
            title=":bulb: Response",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()


def print_cost(cost) -> None:
    savings_pct = cost.savings_percentage
    if savings_pct >= 90:
        badge = "[bold green]:tada: AMAZING SAVINGS[/bold green]"
    elif savings_pct >= 50:
        badge = "[bold yellow]:heavy_check_mark: GREAT SAVINGS[/bold yellow]"
    else:
        badge = "[dim]Some savings[/dim]"

    console.print(
        Panel(
            f"[green]:moneybag: Actual cost:          ${cost.actual_cost:.4f}[/green]\n"
            f"[red]:x: Would cost (GPT-4):  ${cost.would_have_cost:.4f}[/red]\n"
            f"[bold green]:sparkles: You saved:            ${cost.savings:.4f} ({cost.savings_percentage:.0f}%)[/bold green]\n"
            f"{badge}",
            title=":money_with_wings: Cost Analysis",
            border_style="yellow",
            padding=(0, 1),
        )
    )
    console.print()


def print_hop_time(latency_ms: int) -> None:
    if latency_ms < 500:
        color = "green"
        rating = ":rocket: Blazing fast!"
    elif latency_ms < 1000:
        color = "yellow"
        rating = ":thumbsup: Fast"
    else:
        color = "white"
        rating = ":clock1: Good"
    console.print(f"  :frog: Hopped in [bold {color}]{latency_ms}ms[/bold {color}]  {rating}")
    console.print()


def print_benchmark_results(results: dict) -> None:
    table = Table(
        title=":bar_chart: Benchmark Results",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Metric", style="bold white", min_width=16)
    table.add_column(":ledger: GPT-4 Only", style="red", min_width=14)
    table.add_column(":frog: ModelHop", style="green", min_width=14)
    table.add_column(":sparkles: Savings", style="yellow", min_width=14)

    table.add_row(
        "Total Cost",
        f"${results['gpt4_cost']:.2f}",
        f"${results['modelhop_cost']:.2f}",
        f"{results['savings_pct']:.1f}%",
    )
    table.add_row(
        "Avg Cost/Query",
        f"${results['gpt4_avg']:.4f}",
        f"${results['modelhop_avg']:.4f}",
        f"{results['savings_pct']:.1f}%",
    )
    table.add_row(
        "Avg Latency",
        f"{results['gpt4_latency']:.1f}s",
        f"{results['modelhop_latency']:.1f}s",
        f"{results['latency_improvement']:.1f}%",
    )
    gpt4_quality = results.get("gpt4_quality")
    quality_delta = results.get("quality_delta")
    gpt4_quality_str = "n/a" if gpt4_quality is None else f"{gpt4_quality:.0f}%"
    quality_delta_str = "n/a" if quality_delta is None else f"{quality_delta:.1f}%"
    table.add_row(
        "Quality Score",
        gpt4_quality_str,
        f"{results['modelhop_quality']:.0f}%",
        quality_delta_str,
    )

    console.print(table)
    if gpt4_quality is None:
        console.print(
            "[dim]Quality = routed-response confidence. GPT-4 baseline not measured: "
            "no premium provider was available.[/dim]"
        )
    console.print()


def print_distribution(distribution: dict) -> None:
    console.print("  :chart_with_upwards_trend: [bold]Model Distribution[/bold]")
    console.print()
    for model, percentage in sorted(distribution.items(), key=lambda x: -x[1]):
        bar_length = int(percentage / 5)
        if is_plain_output():
            bar = "#" * bar_length + "-" * (20 - bar_length)
        else:
            bar = ":green_circle:" * bar_length + ":black_circle:" * (20 - bar_length)
        console.print(f"     {model}: [green]{percentage}%[/green]  {bar}")
    console.print()


def print_hop_score(score: int) -> None:
    if score >= 90:
        color = "green"
        badge = ":trophy: EXCELLENT"
    elif score >= 70:
        color = "green"
        badge = ":medal: GOOD"
    elif score >= 50:
        color = "yellow"
        badge = ":chart_with_upwards_trend: AVERAGE"
    else:
        color = "red"
        badge = ":warning: NEEDS IMPROVEMENT"

    console.print(
        Panel(
            f"[bold {color}]{score}/100[/]  {badge}",
            title=":frog: Hop Score",
            border_style=color,
            padding=(0, 2),
        )
    )
    console.print()
