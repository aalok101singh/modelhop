import click
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)


@click.command()
def example() -> None:
    """:frog: Show example queries to try."""
    console.print()
    console.print(
        Panel(
            "[bold green]:frog: Example Queries[/bold green]\n"
            "[dim]Copy-paste these to see ModelHop in action![/dim]",
            border_style="green",
            padding=(0, 2),
        )
    )
    console.print()

    examples = [
        {
            "query": "How do I reset my password?",
            "tier": "FREE",
            "why": "Simple FAQ - any model can handle it",
            "color": "green",
        },
        {
            "query": "Explain the difference between TCP and UDP",
            "tier": "FREE",
            "why": "Technical explanation - still free tier capable",
            "color": "green",
        },
        {
            "query": "Write a Python function to implement quicksort with detailed comments",
            "tier": "PREMIUM",
            "why": "Complex code generation - may need premium model",
            "color": "red",
        },
        {
            "query": "This is ridiculous, I've been waiting 3 hours for support!",
            "tier": "VARIES",
            "why": "Frustrated tone detected - may escalate for better handling",
            "color": "yellow",
        },
        {
            "query": "Draft a professional email declining a meeting invitation politely",
            "tier": "FREE",
            "why": "Creative writing - free models handle this well",
            "color": "green",
        },
    ]

    for i, ex in enumerate(examples, 1):
        console.print(
            Panel(
                f"[bold cyan]\"{ex['query']}\"[/bold cyan]\n\n"
                f"  Tier: [{ex['color']}]{ex['tier']}[/{ex['color']}]  |  Why: [dim]{ex['why']}[/dim]",
                title=f":speech_balloon: Example {i}",
                border_style=ex["color"],
                padding=(0, 1),
            )
        )
        console.print()

    console.print(
        Panel(
            "[bold]Run any of these with:[/bold]\n\n"
            '  [cyan]modelhop route "paste the query here"[/cyan]\n\n'
            "[bold]Or try the shorthand:[/bold]\n\n"
            '  [cyan]modelhop r "paste the query here"[/cyan]',
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()
