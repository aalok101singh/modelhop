import asyncio
import json as json_mod

import click
from rich.table import Table

from ..display import get_console, tier_color
from ..provider_errors import describe_provider_error

console = get_console()


async def _test_provider(provider) -> tuple:
    """Returns (ok, detail): honest reason instead of a bare failure."""
    try:
        await provider.generate("Hi", max_tokens=5)
        return True, "connected"
    except Exception as exc:
        _kind, msg = describe_provider_error(exc, "", getattr(provider, "model", "") or "")
        return False, msg


@click.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def providers(json_output: bool) -> None:
    """:frog: List available providers and their status."""
    from modelhop import ModelHop

    mh = ModelHop()

    if json_output:
        output = []
        for model in mh.registry.get_models():
            provider = mh.registry.get_provider(model.name)
            if provider:
                connected, detail = asyncio.run(_test_provider(provider))
                status = "connected" if connected else "failed"
            else:
                status, detail = "no_key", "no API key configured"
            output.append(
                {
                    "name": model.name,
                    "provider": model.provider,
                    "model": model.model,
                    "tier": model.tier.value,
                    "status": status,
                    "detail": detail,
                }
            )
        print(json_mod.dumps(output, indent=2))  # noqa: T201 - raw JSON, no rich wrap
    else:
        table = Table(
            title=":frog: Model Providers",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Provider", style="bold white", min_width=10)
        table.add_column("Model", style="green", min_width=22)
        table.add_column("Tier", min_width=10)
        table.add_column("Status", min_width=14)

        for model in mh.registry.get_models():
            provider = mh.registry.get_provider(model.name)
            color = tier_color(model.tier.value)
            if provider:
                connected, detail = asyncio.run(_test_provider(provider))
                if connected:
                    status = "[green]:white_check_mark: Connected[/green]"
                else:
                    status = f"[red]:x: Failed - {detail}[/red]"
            else:
                status = "[yellow]:key: No API Key[/yellow]"
            table.add_row(
                model.provider, model.model, f"[{color}]{model.tier.value}[/{color}]", status
            )

        console.print()
        console.print(table)
        console.print()
