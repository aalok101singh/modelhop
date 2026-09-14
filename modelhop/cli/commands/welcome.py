import click
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)


@click.command()
def welcome() -> None:
    """:frog: Welcome to ModelHop - quick setup guide."""
    import os
    from pathlib import Path

    console.print()
    console.print(Panel(
        "[bold green]:frog: Welcome to ModelHop![/bold green]\n\n"
        "ModelHop routes your LLM queries to the [bold]cheapest capable model[/bold],\n"
        "saving you 60-90%% on API costs while maintaining quality.",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()

    checks = []

    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if groq_key or gemini_key or openai_key:
        if groq_key:
            checks.append("[green]:white_check_mark: GROQ_API_KEY set (free tier)[/green]")
        if gemini_key:
            checks.append("[green]:white_check_mark: GEMINI_API_KEY set (free tier)[/green]")
        if openai_key:
            checks.append("[green]:white_check_mark: OPENAI_API_KEY set (premium tier)[/green]")
    else:
        checks.append("[red]:x: No API keys found[/red]")
        checks.append("   Run [cyan]modelhop setup[/cyan] to configure")

    env_path = Path(".env")
    if env_path.exists():
        checks.append("[green]:white_check_mark: .env file found[/green]")

    config_path = Path("modelhop.yaml")
    if config_path.exists():
        checks.append("[green]:white_check_mark: modelhop.yaml found[/green]")
    else:
        checks.append("[yellow]:warning: modelhop.yaml not found[/yellow]")
        checks.append("   Run [cyan]modelhop init[/cyan] to create it")

    console.print(Panel(
        "\n".join(checks),
        title=":mag: Setup Check",
        border_style="cyan",
        padding=(0, 1),
    ))
    console.print()

    lines = [
        "[bold]Try your first query:[/bold]",
        "",
        '  [cyan]modelhop r "How do I reset my password?"[/cyan]',
        "",
        "[bold]Or explore:[/bold]",
        "",
        "  [cyan]modelhop setup[/cyan]     - Configure API keys",
        "  [cyan]modelhop example[/cyan]   - See example queries",
        "  [cyan]modelhop cheat[/cyan]     - Quick reference card",
        "  [cyan]modelhop providers[/cyan] - Check connected providers",
        "  [cyan]modelhop stats[/cyan]     - View your savings",
    ]

    console.print(Panel(
        "\n".join(lines),
        title=":rocket: Quick Start",
        border_style="green",
        padding=(0, 1),
    ))
    console.print()
