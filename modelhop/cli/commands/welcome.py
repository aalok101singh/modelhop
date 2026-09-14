import asyncio

import click
from rich.console import Console
from rich.panel import Panel

console = Console(force_terminal=True)

PROBE_TIMEOUT = 5


async def _test_groq(api_key: str, model: str) -> bool:
    from groq import AsyncGroq

    client = AsyncGroq(api_key=api_key, max_retries=0)
    await asyncio.wait_for(
        client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
        ),
        timeout=PROBE_TIMEOUT,
    )
    return True


async def _test_gemini(api_key: str, model: str) -> bool:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)
    await asyncio.wait_for(m.generate_content_async("Hi"), timeout=PROBE_TIMEOUT)
    return True


async def _test_openai(api_key: str, model: str) -> bool:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=PROBE_TIMEOUT)
    await client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
    )
    return True


async def _probe_provider(provider: str, api_key: str, model: str) -> bool:
    try:
        if provider == "groq":
            return await _test_groq(api_key, model)
        elif provider == "gemini":
            return await _test_gemini(api_key, model)
        elif provider == "openai":
            return await _test_openai(api_key, model)
    except Exception:
        return False
    return False


@click.command()
def welcome() -> None:
    """:frog: Welcome to ModelHop - quick setup guide."""
    import os
    from pathlib import Path

    from modelhop.config import Config

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

    cfg = Config()
    models = cfg.get_models()

    seen_providers = {}
    for m in models:
        if m.provider not in seen_providers:
            seen_providers[m.provider] = m

    async def _run_all_probes():
        results = {}
        for provider, m in seen_providers.items():
            api_key = os.environ.get(m.api_key_env, "")
            if not api_key:
                results[provider] = None
                continue
            results[provider] = await _probe_provider(provider, api_key, m.model)
        return results

    results = asyncio.run(_run_all_probes()) if seen_providers else {}

    any_key_found = False
    for provider, m in seen_providers.items():
        api_key = os.environ.get(m.api_key_env, "")
        if not api_key:
            continue
        any_key_found = True
        ok = results.get(provider)
        provider_upper = provider.upper()
        if ok:
            checks.append(
                f"[green]:white_check_mark: {provider_upper} connected ({m.model})[/green]"
            )
        else:
            checks.append(
                f"[red]:x: {provider_upper} key invalid or model {m.model} unreachable[/red]"
            )

    if not any_key_found:
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
