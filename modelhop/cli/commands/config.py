import click
from rich.panel import Panel

from ..display import get_console

console = get_console()


@click.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def config(json_output: bool) -> None:
    """:frog: Show current configuration."""
    import json as json_mod

    import yaml

    from modelhop.config import Config

    cfg = Config()

    if json_output:
        print(json_mod.dumps(cfg.config, indent=2))  # noqa: T201 - raw JSON, no rich wrap
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
