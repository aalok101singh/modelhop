import click
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)


@click.command()
def cheat() -> None:
    """:frog: Quick reference card for ModelHop."""
    console.print()
    console.print(Panel(
        "[bold green]:frog: ModelHop Quick Reference[/bold green]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()

    console.print(Panel(
        "[bold]:zap: Core Commands[/bold]\n\n"
        "  [cyan]modelhop route \"query\"[/cyan]   Route a query (saves money)\n"
        "  [cyan]modelhop r \"query\"[/cyan]        Short alias for route\n"
        "  [cyan]modelhop init[/cyan]              Create config file\n"
        "  [cyan]modelhop i[/cyan]                 Short alias for init",
        title=":star: Essential",
        border_style="yellow",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:bar_chart: Insights[/bold]\n\n"
        "  [cyan]modelhop stats[/cyan]             View savings & metrics\n"
        "  [cyan]modelhop s[/cyan]                 Short alias for stats\n"
        "  [cyan]modelhop history[/cyan]           See recent routing decisions\n"
        "  [cyan]modelhop h[/cyan]                 Short alias for history\n"
        "  [cyan]modelhop benchmark[/cyan]         Run cost comparison test\n"
        "  [cyan]modelhop b[/cyan]                 Short alias for benchmark",
        title=":chart_with_upwards_trend: Track",
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:gear: Configuration[/bold]\n\n"
        "  [cyan]modelhop providers[/cyan]         List providers & API status\n"
        "  [cyan]modelhop p[/cyan]                 Short alias for providers\n"
        "  [cyan]modelhop config[/cyan]            Show current config\n"
        "  [cyan]modelhop c[/cyan]                 Short alias for config\n"
        "  [cyan]modelhop shield status[/cyan]     Quality assurance status",
        title=":wrench: Setup",
        border_style="magenta",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:earth_africa: Community[/bold]\n\n"
        "  [cyan]modelhop hub list[/cyan]          Browse community configs\n"
        "  [cyan]modelhop hub download <name>[/cyan]  Download a config\n"
        "  [cyan]modelhop welcome[/cyan]           First-time setup guide\n"
        "  [cyan]modelhop example[/cyan]           See example queries",
        title=":handshake: Discover",
        border_style="green",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:gear: Useful Flags[/bold]\n\n"
        "  [cyan]--json[/cyan]           Output as JSON (for scripts)\n"
        "  [cyan]--verbose[/cyan]        Show full routing trace\n"
        "  [cyan]--model <name>[/cyan]   Force a specific model\n"
        "  [cyan]--help[/cyan]           Show help for any command",
        title=":hammer_and_wrench: Flags",
        border_style="white",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:key: Environment Variables[/bold]\n\n"
        "  [cyan]$env:GROQ_API_KEY[/cyan]      Free tier (recommended to start)\n"
        "  [cyan]$env:GEMINI_API_KEY[/cyan]    Free tier\n"
        "  [cyan]$env:OPENAI_API_KEY[/cyan]    Premium tier",
        title=":lock: API Keys",
        border_style="red",
        padding=(0, 1),
    ))
    console.print()

    console.print(Panel(
        "[bold]:rocket: Example Workflow[/bold]\n\n"
        "  [dim]# 1. Set your API key (PowerShell)[/dim]\n"
        "  [cyan]$env:GROQ_API_KEY=\"gsk_your_key\"[/cyan]\n\n"
        "  [dim]# 2. Initialize config[/dim]\n"
        "  [cyan]modelhop init[/cyan]\n\n"
        "  [dim]# 3. Route a query[/dim]\n"
        "  [cyan]modelhop route \"How do I reset my password?\"[/cyan]\n\n"
        "  [dim]# 4. Check your savings[/dim]\n"
        "  [cyan]modelhop stats[/cyan]",
        title=":books: Workflow",
        border_style="yellow",
        padding=(0, 1),
    ))
    console.print()
