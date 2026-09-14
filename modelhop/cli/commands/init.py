import os
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)


@click.command()
@click.option("--path", "-p", default="modelhop.yaml", help="Path for config file")
@click.option("--setup/--no-setup", default=True, help="Run API key setup after creating config")
@click.pass_context
def init(ctx: click.Context, path: str, setup: bool) -> None:
    """:frog: Initialize ModelHop configuration."""
    from modelhop.config import EXAMPLE_CONFIG
    import yaml

    config_path = Path(path)
    created_new = False

    if config_path.exists():
        console.print()
        console.print(Panel(
            f"[yellow]Config file already exists at [cyan]{path}[/cyan][/yellow]",
            title=":warning: File Exists",
            border_style="yellow",
        ))
        if not click.confirm("Overwrite?"):
            console.print("[dim]Keeping existing config.[/dim]")
            console.print()
            if setup and _should_setup_keys():
                _run_setup(ctx)
            return

    with open(config_path, "w") as f:
        yaml.dump(EXAMPLE_CONFIG, f, default_flow_style=False)

    created_new = True
    console.print()
    console.print(Panel(
        f"[bold green]:white_check_mark: Created [cyan]{path}[/cyan][/bold green]",
        title=":frog: Config Created",
        border_style="green",
        padding=(0, 1),
    ))
    console.print()

    if setup and _should_setup_keys():
        _run_setup(ctx)
    else:
        console.print(Panel(
            "[bold]Next steps:[/bold]\n\n"
            "  1. Set API keys: [cyan]modelhop setup[/cyan]\n"
            "  2. Route a query: [cyan]modelhop r \"your question\"[/cyan]\n"
            "  3. See examples:  [cyan]modelhop example[/cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
        console.print()


def _should_setup_keys() -> bool:
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r") as f:
            content = f.read()
        if "GROQ_API_KEY=" in content or "OPENAI_API_KEY=" in content or "GEMINI_API_KEY=" in content:
            return False

    has_env_keys = any(os.environ.get(k) for k in ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"])
    if has_env_keys:
        return False

    return click.confirm("Would you like to configure API keys now?", default=True)


def _run_setup(ctx: click.Context) -> None:
    from .setup import setup
    ctx.invoke(setup)
