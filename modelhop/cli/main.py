import click

from .._version import get_version
from .display import get_console

console = get_console(force_terminal=True)

__version__ = get_version()


def _ensure_utf8_stdio() -> None:
    """Force UTF-8 on stdio so emoji output survives redirection on Windows.

    Without this, `modelhop welcome > out.txt` (or any pipe) crashes with
    UnicodeEncodeError when the active code page is not UTF-8 (e.g. cp1252),
    because rich writes emoji (e.g. the frog) straight to the pipe.
    """
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name=":frog: ModelHop")
@click.pass_context
def cli(ctx) -> None:
    """:frog: ModelHop - Save 60-90%% on LLM costs by hopping to the right model."""
    _ensure_utf8_stdio()
    if ctx.invoked_subcommand is None:
        ctx.invoke(welcome)


from .commands.benchmark import benchmark
from .commands.calibrate import calibrate
from .commands.cheat import cheat
from .commands.config import config
from .commands.eval_cmd import eval as eval_cmd
from .commands.example import example
from .commands.history import history
from .commands.hub_cmd import hub
from .commands.init import init
from .commands.providers_cmd import providers
from .commands.route import route
from .commands.serve_cmd import serve
from .commands.setup import setup
from .commands.shield_cmd import shield
from .commands.stats import stats
from .commands.welcome import welcome

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
cli.add_command(cheat)
cli.add_command(eval_cmd)
cli.add_command(calibrate)
cli.add_command(serve)

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
