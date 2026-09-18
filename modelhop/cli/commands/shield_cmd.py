import json as json_mod

import click
from rich.panel import Panel

from ..display import get_console

console = get_console()


@click.group(invoke_without_command=True)
@click.pass_context
def shield(ctx) -> None:
    """:frog: ModelHop Shield - Quality assurance."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@shield.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def status(json_output: bool) -> None:
    """:frog: Show Shield quality status."""
    from modelhop import ModelHop

    mh = ModelHop()
    shield_status = mh.shield.get_status()
    recommendations = mh.shield.get_recommendations()

    if json_output:
        output = {
            "active": shield_status.active,
            "quality_score": shield_status.quality_score,
            "consensus_rate": shield_status.consensus_rate,
            "alerts": shield_status.alerts,
            "adjustments_today": shield_status.adjustments_today,
            "recommendations": recommendations,
        }
        print(json_mod.dumps(output, indent=2))  # noqa: T201 - raw JSON, no rich wrap
    else:
        active_color = "green" if shield_status.active else "red"
        active_icon = ":white_check_mark:" if shield_status.active else ":x:"

        content = (
            f"[{active_color}]{active_icon} Active: {'Yes' if shield_status.active else 'No'}[/{active_color}]\n\n"
            f":chart_with_upwards_trend: [bold]Quality Score:[/bold] {shield_status.quality_score:.2f}\n"
            f":link: [bold]Consensus Rate:[/bold] {shield_status.consensus_rate:.2f}\n"
            f":gear: [bold]Adjustments Today:[/bold] {shield_status.adjustments_today}"
        )

        if shield_status.alerts:
            content += "\n\n:warning: [bold yellow]Recent Alerts:[/bold yellow]\n"
            for alert in shield_status.alerts:
                content += f"  :warning: {alert}\n"

        if recommendations:
            content += "\n:bulb: [bold cyan]Recommendations:[/bold cyan]\n"
            for rec in recommendations:
                content += f"  :bulb: {rec}\n"

        console.print()
        console.print(
            Panel(
                content,
                title=":shield: ModelHop Shield",
                border_style="green" if shield_status.active else "red",
                padding=(0, 1),
            )
        )
        console.print()
