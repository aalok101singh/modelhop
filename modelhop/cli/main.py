import click
from rich.console import Console
from importlib.metadata import version as get_version
from pathlib import Path

console = Console(force_terminal=True)

try:
    __version__ = get_version("modelhop")
except Exception:
    __version__ = "0.0.0"


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name=":frog: ModelHop")
@click.pass_context
def cli(ctx) -> None:
    """:frog: ModelHop - Save 60-90%% on LLM costs by hopping to the right model."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(welcome)


from .commands.route import route
from .commands.init import init
from .commands.benchmark import benchmark
from .commands.config import config
from .commands.stats import stats
from .commands.history import history
from .commands.providers_cmd import providers
from .commands.shield_cmd import shield
from .commands.hub_cmd import hub
from .commands.welcome import welcome
from .commands.example import example
from .commands.cheat import cheat
from .commands.setup import setup

cli.add_command(route)
cli.add_command(init)
cli.add_command(benchmark)
cli.add_command(config)
cli.add_command(stats)
cli.add_command(history)
cli.add_command(providers)
cli.add_command(shield)
cli.add_command(hub)
cli.add_command(welcome)
cli.add_command(example)
cli.add_command(setup)

# Short aliases
cli.add_command(route, "r")
cli.add_command(stats, "s")
cli.add_command(history, "h")
cli.add_command(providers, "p")
cli.add_command(benchmark, "b")
cli.add_command(config, "c")
cli.add_command(init, "i")
cli.add_command(example, "e")
cli.add_command(setup, "set")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
