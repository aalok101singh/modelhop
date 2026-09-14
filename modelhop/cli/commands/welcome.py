import asyncio

import click
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)


async def _test_key(provider: str, api_key: str, model: str) -> bool:
    try:
        if provider == "groq":
            from groq import AsyncGroq

            client = AsyncGroq(api_key=api_key)
            await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
            )
            return True
        elif provider == "gemini":
            import os

            os.environ["GOOGLE_API_KEY"] = api_key
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model)
            await m.generate_content_async("Hi")
            return True
        elif provider == "openai":
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=api_key)
            await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
            )
            return True
    except Exception:
        return False
    return False


@click.command()
def welcome() -> None:
    """:frog: Welcome to ModelHop - quick setup guide."""
    import os
    from pathlib import Path

    console.print()
    console.print(
        Panel(
            "[bold green]:frog: Welcome to ModelHop![/bold green]\n\n"
            "ModelHop routes your LLM queries to the [bold]cheapest capable model[/bold],\n"
            "saving you 60-90%% on API costs while maintaining quality.",
            border_style="green",
            padding=(0, 2),
        )
    )
    console.print()

    checks = []

    groq_key = os.environ.get("GROQ_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    has_any_key = groq_key or gemini_key or openai_key

    if has_any_key:
        if groq_key:
            ok = asyncio.run(_test_key("groq", groq_key, "qwen/qwen3.8-27b"))
            if ok:
                checks.append(
                    "[green]:white_check_mark: GROQ_API_KEY connected (free tier)[/green]"
                )
            else:
                checks.append("[red]:x: GROQ_API_KEY invalid or unreachable[/red]")
        if gemini_key:
            ok = asyncio.run(_test_key("gemini", gemini_key, "gemini-3.6-flash"))
            if ok:
                checks.append(
                    "[green]:white_check_mark: GEMINI_API_KEY connected (free tier)[/green]"
                )
            else:
                checks.append("[red]:x: GEMINI_API_KEY invalid or unreachable[/red]")
        if openai_key:
            ok = asyncio.run(_test_key("openai", openai_key, "gpt-4"))
            if ok:
                checks.append(
                    "[green]:white_check_mark: OPENAI_API_KEY connected (premium tier)[/green]"
                )
            else:
                checks.append("[red]:x: OPENAI_API_KEY invalid or unreachable[/red]")
    else:
        checks.append("[red]:x: No API keys found[/red]")
        checks.append("   Run [cyan]modelhop setup[/cyan] to configure")

    env_path = Path(".env")
    if env_path.exists():
        checks.append("[green]:white_check_mark: .env file found[/green]")

    config_path = Path("modelhop.yaml")
    if config_path.exists():
        checks.append("[green]:white_check_mark: modelhop.yaml found[/green]")
    else:
        checks.append("[yellow]:warning: modelhop.yaml not found[/yellow]")
        checks.append("   Run [cyan]modelhop init[/cyan] to create it")

    console.print(
        Panel(
            "\n".join(checks),
            title=":mag: Setup Check",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    lines = [
        "[bold]Try your first query:[/bold]",
        "",
        '  [cyan]modelhop r "How do I reset my password?"[/cyan]',
        "",
        "[bold]Or explore:[/bold]",
        "",
        "  [cyan]modelhop setup[/cyan]     - Configure API keys",
        "  [cyan]modelhop example[/cyan]   - See example queries",
        "  [cyan]modelhop cheat[/cyan]     - Quick reference card",
        "  [cyan]modelhop providers[/cyan] - Check connected providers",
        "  [cyan]modelhop stats[/cyan]     - View your savings",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title=":rocket: Quick Start",
            border_style="green",
            padding=(0, 1),
        )
    )
    console.print()
