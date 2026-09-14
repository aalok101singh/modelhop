import asyncio
import json as json_mod

import click
from rich.console import Console
from rich.table import Table

console = Console()


async def _test_provider(provider) -> bool:
    try:
        await provider.generate("Hi", max_tokens=5)
        return True
    except Exception:
        return False


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
                connected = asyncio.run(_test_provider(provider))
                status = "connected" if connected else "failed"
            else:
                status = "no_key"
            output.append(
                {
                    "name": model.name,
                    "provider": model.provider,
                    "model": model.model,
                    "tier": model.tier.value,
                    "status": status,
                }
            )
        console.print(json_mod.dumps(output, indent=2))
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

        tier_colors = {"free": "green", "mid": "yellow", "premium": "red"}

        for model in mh.registry.get_models():
            provider = mh.registry.get_provider(model.name)
            color = tier_colors.get(model.tier.value, "white")
            if provider:
                connected = asyncio.run(_test_provider(provider))
                if connected:
                    status = "[green]:white_check_mark: Connected[/green]"
                else:
                    status = "[red]:x: Failed[/red]"
            else:
                status = "[yellow]:key: No API Key[/yellow]"
            table.add_row(
                model.provider, model.model, f"[{color}]{model.tier.value}[/{color}]", status
            )

        console.print()
        console.print(table)
        console.print()
