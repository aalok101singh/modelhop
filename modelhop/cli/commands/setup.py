import asyncio
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from ...config import _load_env_file

console = Console(force_terminal=True)

ENV_PATH = Path(".env")


def _save_env(keys: dict) -> None:
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r") as f:
            lines = [
                line
                for line in f.readlines()
                if not any(line.strip().startswith(k) for k in keys if keys[k])
            ]

    for key, value in keys.items():
        if value:
            lines.append(f'{key}="{value}"\n')

    with open(ENV_PATH, "w") as f:
        f.writelines(lines)


def _update_config_models(keys: dict) -> None:
    import yaml

    config_path = Path("modelhop.yaml")
    if not config_path.exists():
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    models = config.get("models", [])

    groq_models = [m for m in models if m.get("provider") == "groq"]
    if keys.get("GROQ_API_KEY") and not groq_models:
        models.append(
            {
                "name": "groq-qwen3-8-27b",
                "provider": "groq",
                "model": "qwen/qwen3.8-27b",
                "tier": "free",
                "capabilities": ["faq", "general", "classification", "reasoning", "coding"],
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "api_key_env": "GROQ_API_KEY",
            }
        )

    gemini_models = [m for m in models if m.get("provider") == "gemini"]
    if keys.get("GEMINI_API_KEY") and not gemini_models:
        models.append(
            {
                "name": "gemini-3.6-flash",
                "provider": "gemini",
                "model": "gemini-3.6-flash",
                "tier": "free",
                "capabilities": ["faq", "general", "reasoning"],
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "api_key_env": "GEMINI_API_KEY",
            }
        )

    openai_models = [m for m in models if m.get("provider") == "openai"]
    if keys.get("OPENAI_API_KEY") and not openai_models:
        models.append(
            {
                "name": "openai-gpt-4",
                "provider": "openai",
                "model": "gpt-4",
                "tier": "premium",
                "capabilities": ["reasoning", "coding", "analysis", "creative"],
                "cost_per_1k_input": 0.03,
                "cost_per_1k_output": 0.06,
                "api_key_env": "OPENAI_API_KEY",
            }
        )

    config["models"] = models
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


async def _test_connection(provider_name: str, api_key: str, model: str) -> bool:
    try:
        if provider_name == "groq":
            from groq import AsyncGroq

            client = AsyncGroq(api_key=api_key)
            await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
            )
            return True
        elif provider_name == "gemini":
            import google.generativeai as genai

            genai.configure(api_key=api_key)
            m = genai.GenerativeModel(model)
            await m.generate_content_async("Hi")
            return True
        elif provider_name == "openai":
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
def setup() -> None:
    """:frog: Interactive API key setup wizard."""
    console.print()
    console.print(
        Panel(
            "[bold green]:frog: ModelHop Setup Wizard[/bold green]\n\n"
            "Configure your API keys to start routing queries.\n"
            "Press [cyan]Enter[/cyan] to skip any provider you don't have.",
            border_style="green",
            padding=(0, 2),
        )
    )
    console.print()

    keys = {}

    console.print(
        Panel(
            "[bold]:free: Groq (FREE - Recommended)[/bold]\n"
            "Fast inference, no cost. Get a key at [cyan]console.groq.com[/cyan]\n"
            "Model: [green]qwen/qwen3.8-27b[/green]",
            title="Provider 1 of 3",
            border_style="green",
            padding=(0, 1),
        )
    )
    groq_key = input("  Groq API key: ").strip()
    if groq_key:
        keys["GROQ_API_KEY"] = groq_key
    console.print()

    console.print(
        Panel(
            "[bold]:free: Gemini (FREE)[/bold]\n"
            "Google's free tier. Get a key at [cyan]aistudio.google.com[/cyan]\n"
            "Model: [green]gemini-3.6-flash[/green]",
            title="Provider 2 of 3",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    gemini_key = input("  Gemini API key (or Enter to skip): ").strip()
    if gemini_key:
        keys["GEMINI_API_KEY"] = gemini_key
    console.print()

    console.print(
        Panel(
            "[bold]:crown: OpenAI (PREMIUM)[/bold]\n"
            "GPT-4 for complex queries. Get a key at [cyan]platform.openai.com[/cyan]\n"
            "Model: [red]gpt-4[/red] ($0.03/1K tokens)",
            title="Provider 3 of 3",
            border_style="yellow",
            padding=(0, 1),
        )
    )
    openai_key = input("  OpenAI API key (or Enter to skip): ").strip()
    if openai_key:
        keys["OPENAI_API_KEY"] = openai_key
    console.print()

    if not keys:
        console.print(
            Panel(
                "[yellow]No API keys provided.[/yellow]\n\n"
                "You can run [cyan]modelhop setup[/cyan] again anytime.",
                title=":warning: Skipped",
                border_style="yellow",
            )
        )
        console.print()
        return

    _save_env(keys)
    _update_config_models(keys)
    _load_env_file()

    console.print("[bold]Testing connections...[/bold]\n")

    results = []
    any_success = False

    if "GROQ_API_KEY" in keys:
        ok = asyncio.run(_test_connection("groq", keys["GROQ_API_KEY"], "qwen/qwen3.8-27b"))
        status = (
            "[green]:white_check_mark: Connected[/green]"
            if ok
            else "[red]:x: Failed - check your key[/red]"
        )
        results.append(f"  Groq   : {status}")
        if ok:
            any_success = True

    if "GEMINI_API_KEY" in keys:
        ok = asyncio.run(_test_connection("gemini", keys["GEMINI_API_KEY"], "gemini-3.6-flash"))
        status = (
            "[green]:white_check_mark: Connected[/green]"
            if ok
            else "[red]:x: Failed - check your key[/red]"
        )
        results.append(f"  Gemini : {status}")
        if ok:
            any_success = True

    if "OPENAI_API_KEY" in keys:
        ok = asyncio.run(_test_connection("openai", keys["OPENAI_API_KEY"], "gpt-4"))
        status = (
            "[green]:white_check_mark: Connected[/green]"
            if ok
            else "[red]:x: Failed - check your key[/red]"
        )
        results.append(f"  OpenAI : {status}")
        if ok:
            any_success = True

    console.print(
        Panel(
            "\n".join(results),
            title=":mag: Connection Results",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    if not any_success:
        console.print(
            Panel(
                "[bold red]:x: No valid API keys![/bold red]\n\n"
                "All keys failed. Check your keys and try again.\n\n"
                "[bold]Get free keys at:[/bold]\n"
                "  Groq   : [cyan]console.groq.com[/cyan]\n"
                "  Gemini : [cyan]aistudio.google.com[/cyan]",
                title=":warning: Setup Incomplete",
                border_style="red",
                padding=(0, 1),
            )
        )
        console.print()
        return

    console.print(
        Panel(
            "[bold green]:white_check_mark: Setup complete![/bold green]\n\n"
            "[bold]Try it now:[/bold]\n"
            '  [cyan]modelhop r "How do I reset my password?"[/cyan]\n\n'
            "[bold]Or explore:[/bold]\n"
            "  [cyan]modelhop example[/cyan]  - See example queries\n"
            "  [cyan]modelhop cheat[/cyan]    - Quick reference card",
            title=":frog: Ready to Hop!",
            border_style="green",
            padding=(0, 1),
        )
    )
    console.print()
