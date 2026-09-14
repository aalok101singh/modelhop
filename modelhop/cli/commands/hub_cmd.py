import click
import json as json_mod
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def hub(ctx) -> None:
    """:frog: ModelHop Hub - Community routing configs."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_configs)


@hub.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_configs(json_output: bool) -> None:
    """:frog: List available community configs."""
    from modelhop.hub.hub import Hub

    hub_instance = Hub()
    configs = hub_instance.list_configs()

    if json_output:
        output = []
        for config in configs:
            output.append({
                "name": config.name,
                "author": config.author,
                "description": config.description,
                "rating": config.rating,
                "downloads": config.downloads,
                "tags": config.tags
            })
        console.print(json_mod.dumps(output, indent=2))
    else:
        if not configs:
            console.print()
            console.print(Panel(
                "[yellow]No community configs found[/yellow]",
                title=":frog: Community Hub",
                border_style="cyan",
            ))
            console.print()
            return

        table = Table(
            title=":frog: Community Configurations",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            padding=(0, 1),
        )
        table.add_column("Name", style="green", min_width=16)
        table.add_column("Author", min_width=18)
        table.add_column("Description", max_width=40, min_width=20)
        table.add_column(":star: Rating", min_width=10)
        table.add_column(":arrow_down: Downloads", min_width=12)
        table.add_column("Tags", min_width=20)

        for config in configs:
            table.add_row(
                config.name,
                config.author,
                config.description[:40] + "..." if len(config.description) > 40 else config.description,
                f":star: {config.rating:.1f}",
                str(config.downloads),
                ", ".join(config.tags[:3])
            )

        console.print()
        console.print(table)
        console.print()


@hub.command("download")
@click.argument("name")
@click.option("--destination", "-d", default="modelhop.yaml", help="Destination file")
def download(name: str, destination: str) -> None:
    """:frog: Download a community config."""
    from modelhop.hub.hub import Hub

    hub_instance = Hub()
    success = hub_instance.download_config(name, destination)

    if success:
        console.print()
        console.print(Panel(
            f"[green]:white_check_mark: Downloaded [bold]{name}[/bold] to [cyan]{destination}[/cyan][/green]",
            title=":frog: Config Downloaded",
            border_style="green",
        ))
        console.print()
    else:
        console.print()
        console.print(Panel(
            f"[red]:x: Config [bold]{name}[/bold] not found[/red]\n\n"
            "Run [cyan]modelhop hub list[/cyan] to see available configs.",
            title=":warning: Not Found",
            border_style="red",
        ))
        console.print()
