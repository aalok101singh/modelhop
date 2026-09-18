import asyncio
from pathlib import Path

import click
from rich.panel import Panel

from ...config import _load_env_file
from ..display import get_console
from ..provider_errors import PROVIDER_DEFAULT_MODELS, candidate_models, test_connection

console = get_console(force_terminal=True)

ENV_PATH = Path(".env")

PROVIDER_LABELS = {"groq": "Groq", "gemini": "Gemini", "openai": "OpenAI"}
PROVIDER_KEY_ENVS = {
    "groq": "GROQ_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}


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


def _remove_env_keys(names: list) -> None:
    if not ENV_PATH.exists() or not names:
        return
    with open(ENV_PATH, "r") as f:
        lines = [
            line for line in f.readlines() if not any(line.strip().startswith(n) for n in names)
        ]
    with open(ENV_PATH, "w") as f:
        f.writelines(lines)


def _model_slug(model: str) -> str:
    return model.replace("/", "-").replace(".", "").replace("_", "-").lower()


def _configured_model(provider: str) -> str:
    try:
        import yaml

        config_path = Path("modelhop.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
            for m in config.get("models", []):
                if m.get("provider") == provider and m.get("model"):
                    return str(m["model"])
    except Exception:
        pass
    return PROVIDER_DEFAULT_MODELS.get(provider, "")


def _update_config_models(connected: dict) -> None:
    """Wire only providers with a verified working model (add or update)."""
    import yaml

    config_path = Path("modelhop.yaml")
    if not config_path.exists():
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    models = config.get("models", [])

    defaults = {
        "groq": {
            "tier": "free",
            "capabilities": ["faq", "general", "classification", "reasoning", "coding"],
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "api_key_env": "GROQ_API_KEY",
        },
        "gemini": {
            "tier": "free",
            "capabilities": ["faq", "general", "reasoning"],
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
            "api_key_env": "GEMINI_API_KEY",
        },
        "openai": {
            "tier": "premium",
            "capabilities": ["reasoning", "coding", "analysis", "creative"],
            "cost_per_1k_input": 0.03,
            "cost_per_1k_output": 0.06,
            "api_key_env": "OPENAI_API_KEY",
        },
    }

    for provider, model in connected.items():
        if not model:
            continue
        name = f"{provider}-{_model_slug(model)}"
        existing = [m for m in models if m.get("provider") == provider]
        if existing:
            for m in existing:
                m["model"] = model
                m["name"] = name
        else:
            base = dict(defaults.get(provider, {}))
            base.update({"name": name, "provider": provider, "model": model})
            models.append(base)

    config["models"] = models
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def _ensure_config_exists() -> bool:
    """Create modelhop.yaml from defaults when missing. Returns True if created."""
    import yaml

    from ...config import EXAMPLE_CONFIG

    config_path = Path("modelhop.yaml")
    if config_path.exists():
        return False
    try:
        with open(config_path, "w") as f:
            yaml.dump(EXAMPLE_CONFIG, f, default_flow_style=False)
        return True
    except OSError:
        return False


def _remove_config_models(providers: list) -> None:
    """Drop provider models from config (declined => treated as not configured)."""
    import yaml

    config_path = Path("modelhop.yaml")
    if not config_path.exists() or not providers:
        return
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
        models = [m for m in config.get("models", []) if m.get("provider") not in providers]
        config["models"] = models
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception:
        pass


def _probe_alternatives(provider: str, api_key: str, configured: str) -> tuple:
    """Probe fallback catalog. Returns (working_model|None, tried:[(model, detail)])."""
    tried = []
    for model in candidate_models(provider, configured):
        if model == configured:
            continue  # already tested
        ok, _kind, detail = asyncio.run(test_connection(provider, api_key, model))
        tried.append((model, detail))
        if ok:
            return model, tried
    return None, tried


@click.command()
def setup() -> None:
    """:frog: Interactive API key setup wizard."""
    console.print()
    console.print(
        Panel(
            "[bold green]:frog: ModelHop Setup Wizard[/bold green]\n\n"
            "Configure your API keys to start routing queries.\n"
            "Press [cyan]Enter[/cyan] to skip any provider you don't have.\n"
            "If a provider's default model is unavailable, you'll be offered alternatives.",
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
            "Model: [red]gpt-4[/red] ($0.03/1K tokens)\n"
            "Note: OpenAI needs prepaid credits - without them every model fails.",
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

    console.print("[bold]Testing connections...[/bold]\n")

    order = [("groq", "GROQ_API_KEY"), ("gemini", "GEMINI_API_KEY"), ("openai", "OPENAI_API_KEY")]
    connected: dict = {}
    skipped: dict = {}
    save_keys: dict = {}
    purge_env: list = []
    purge_models: list = []
    results = []

    for provider, env_name in order:
        if env_name not in keys:
            continue
        label = PROVIDER_LABELS[provider]
        api_key = keys[env_name]
        configured = _configured_model(provider) or PROVIDER_DEFAULT_MODELS[provider]

        ok, kind, detail = asyncio.run(test_connection(provider, api_key, configured))
        if ok:
            connected[provider] = configured
            save_keys[env_name] = api_key
            results.append(
                f"  {label:<7}: [green]:white_check_mark: Connected ({configured})[/green]"
            )
            continue

        # Failed: show the real reason, then offer model alternatives
        # (except when the key itself is rejected or the network is down).
        if kind == "invalid_key":
            purge_env.append(env_name)
            results.append(f"  {label:<7}: [red]:x: Failed - {detail}[/red]")
            continue
        if kind == "network":
            # Transient: keep the key and existing config for the next run.
            save_keys[env_name] = api_key
            results.append(f"  {label:<7}: [red]:x: Failed - {detail}[/red]")
            continue

        console.print(f"  {label} default model failed: [red]{detail}[/red]")
        tried: list = [(configured, detail)]
        worked = None
        if click.confirm(f"  Try a different {label} model?", default=False):
            worked, catalog_tried = _probe_alternatives(provider, api_key, configured)
            tried.extend(catalog_tried)
            if worked is None and click.confirm(
                f"  Enter a {label} model id manually?", default=False
            ):
                for _ in range(3):
                    manual = input(f"  {label} model id (or Enter to stop): ").strip()
                    if not manual:
                        break
                    ok_m, _kind_m, detail_m = asyncio.run(
                        test_connection(provider, api_key, manual)
                    )
                    tried.append((manual, detail_m))
                    if ok_m:
                        worked = manual
                        break
            if worked:
                connected[provider] = worked
                save_keys[env_name] = api_key
                results.append(
                    f"  {label:<7}: [green]:white_check_mark: " f"Connected ({worked})[/green]"
                )
                continue
            tried_str = "; ".join(f"{m}: {d}" for m, d in tried)
            console.print(f"  [dim]Tried: {tried_str}[/dim]")
            skipped[provider] = detail
            purge_env.append(env_name)
            purge_models.append(provider)
            results.append(f"  {label:<7}: [yellow]:warning: Skipped - not configured[/yellow]")
        else:
            skipped[provider] = detail
            purge_env.append(env_name)
            purge_models.append(provider)
            results.append(f"  {label:<7}: [yellow]:warning: Skipped - not configured[/yellow]")

    _save_env(save_keys)
    _remove_env_keys(purge_env)
    if connected and _ensure_config_exists():
        console.print("[dim]Created modelhop.yaml with defaults.[/dim]\n")
    _update_config_models(connected)
    _remove_config_models(purge_models)
    _load_env_file()

    console.print(
        Panel(
            "\n".join(results),
            title=":mag: Connection Results",
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    if not connected:
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
