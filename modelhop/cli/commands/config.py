import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def config(json_output: bool) -> None:
    """:frog: Show current configuration."""
    import json as json_mod

    import yaml

    from modelhop.config import Config

    cfg = Config()

    if json_output:
        console.print(json_mod.dumps(cfg.config, indent=2))
    else:
        console.print()
        console.print(
            Panel(
                yaml.dump(cfg.config, default_flow_style=False),
                title=":gear: Current Configuration",
                border_style="cyan",
                padding=(0, 1),
            )
        )
        console.print()
