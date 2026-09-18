import asyncio
import json as json_mod

import click
from rich.panel import Panel

from ..._version import get_version
from ..display import get_console, tier_color, tier_emoji

console = get_console()


@click.command()
@click.argument("query")
@click.option("--verbose", "-v", is_flag=True, help="Show full routing trace")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--model", "-m", help="Force specific model")
def route(query: str, verbose: bool, json_output: bool, model: str) -> None:
    ":frog: Route a query to the cheapest capable model."
    asyncio.run(_route_async(query, verbose, json_output, model))


async def _route_async(query: str, verbose: bool, json_output: bool, force_model: str) -> None:
    from modelhop import ModelHop

    mh = ModelHop()

    if not mh.registry.get_available_providers():
        console.print()
        console.print(
            Panel(
                "[bold red]:x: No API keys found![/bold red]\n\n"
                "Set at least one environment variable:\n"
                "  [cyan]$env:GROQ_API_KEY=your-key[/cyan]\n"
                "  [cyan]$env:GEMINI_API_KEY=your-key[/cyan]\n"
                "  [cyan]$env:OPENAI_API_KEY=your-key[/cyan]",
                title=":warning: Configuration Error",
                border_style="red",
            )
        )
        console.print()
        return

    # Relaxed analyzer-provider guard: zero-API heuristic is the default.
    # Only require a provider when explicit LLM analysis is enabled.
    if getattr(mh, "llm_analysis", False) and not mh.analyzer.providers:
        console.print()
        console.print(
            Panel(
                "[bold red]:x: No provider for query analysis![/bold red]\n\n"
                "LLM analysis is enabled (routing.llm_analysis=true) but no API key is set.",
                title=":warning: Configuration Error",
                border_style="red",
            )
        )
        console.print()
        return

    if not json_output:
        console.print()
        console.print(
            Panel(
                f"[bold green]:frog: ModelHop v{get_version()}[/bold green]\n"
                "[dim]Intelligent routing with multi-signal analysis & experience learning[/dim]",
                border_style="green",
                padding=(0, 2),
            )
        )
        console.print()

    # Baseline label comes from config (no hardcoded GPT-4).
    baseline_label = "baseline"
    try:
        baseline_label = (
            mh.cost_tracker.price_book.baseline_model_name(mh.models)
            if getattr(mh.cost_tracker, "price_book", None)
            else "baseline"
        )
    except Exception:
        pass

    try:
        # Thin shell over the SDK brain. Forced model uses the simple router path.
        if force_model:

            features = mh.feature_extractor.extract(query)
            analysis = await mh.analyzer.analyze(query)
            decision = mh.router.route_with_model(force_model, analysis)
            # Generate directly via the forced provider, then wrap as RouteResult.
            provider = mh.registry.get_provider(decision.model.name)
            if provider is None:
                raise RuntimeError(f"Provider not available for {force_model}")
            raw = await provider.generate(query)

            conf = await mh.confidence_engine.check(
                query, raw, provider=None, query_features=features
            )
            cost = mh._route_cost(raw, decision.model, conf)
            from modelhop.core.models import RouteResult

            result = RouteResult(
                response=raw.content,
                model=decision.model.name,
                tier=decision.tier.value,
                reasoning=f"Forced model selection: {force_model}",
                confidence=conf,
                cost=cost,
                candidates=[],
                degraded=False,
                cached=False,
                trust=decision.model.trust,
                verifier=None,
                ledger_id="",
            )
            try:
                object.__setattr__(result, "_provider_response", raw)
            except Exception:
                pass
        else:
            result = await mh.route(query)

        # JSON output keeps all flags valid.
        if json_output:
            output = {
                "query": query,
                "model": result.model,
                "tier": result.tier,
                "reasoning": result.reasoning,
                "response": result.response,
                "confidence": result.confidence.score,
                "confidence_method": result.confidence.method,
                "calibrated": result.confidence.calibrated,
                "cost": result.cost.actual_cost,
                "would_have_cost": result.cost.would_have_cost,
                "savings": result.cost.savings,
                "savings_percentage": result.cost.savings_percentage,
                "tokens_in": result.cost.tokens_in,
                "tokens_out": result.cost.tokens_out,
                "baseline_model": result.cost.baseline_model or baseline_label,
                "aux_calls": result.cost.aux_calls,
                "aux_cost": result.cost.aux_cost,
                "latency_ms": result.latency_ms,
                "degraded": result.degraded,
                "cached": result.cached,
                "trust": result.trust.model_dump() if hasattr(result.trust, "model_dump") else {},
                "verifier": result.verifier.model_dump() if result.verifier else None,
                "ledger_id": result.ledger_id,
                "hop_score": mh.hop_score.get_stats(),
            }
            print(json_mod.dumps(output, indent=2))  # noqa: T201 - raw JSON, no rich wrap
            return

        # Rich panels.
        console.print(
            Panel(result.response, title=":bulb: Response", border_style="cyan", padding=(0, 1))
        )
        console.print()
        # Badges: cached, verified, degraded, trust ZDR.
        badges = []
        if result.cached:
            badges.append("[cyan]cached[/cyan]")
        if result.verifier is not None:
            badges.append(
                "[green]verified[/green]" if result.verifier.passed else "[red]unverified[/red]"
            )
        if result.degraded:
            badges.append(
                "[yellow]:warning: degraded - low confidence "
                f"({result.confidence.score:.2f} < {result.confidence.threshold:.2f}); "
                "used safest fallback[/yellow]"
            )
        try:
            if getattr(result.trust, "zdr", False):
                badges.append("[magenta]trust: ZDR[/magenta]")
        except Exception:
            pass
        if badges:
            console.print("  " + " · ".join(badges))
            console.print()

        cost = result.cost
        savings_pct = cost.savings_percentage
        saved_something = cost.savings > 0
        no_baseline = cost.would_have_cost <= 0
        if no_baseline:
            saved_line = "[dim]:sparkles: You saved:                 " "n/a (free tier only)[/dim]"
            badge = (
                "[dim]No priced baseline - add a premium model "
                "(modelhop setup) to measure savings[/dim]"
            )
        else:
            saved_line = (
                "[bold bright_green]:sparkles: You saved:                 "
                f"${cost.savings:.4f} ({cost.savings_percentage:.0f}%)[/bold bright_green]"
            )
            if savings_pct >= 90:
                badge = "[bold bright_green]:tada: AMAZING SAVINGS[/bold bright_green]"
            elif savings_pct >= 50:
                badge = "[bold yellow]:heavy_check_mark: GREAT SAVINGS[/bold yellow]"
            else:
                badge = "[dim]Some savings[/dim]"
        total_tokens = cost.tokens_in + cost.tokens_out
        console.print(
            Panel(
                f"[green]:moneybag: Actual cost:               ${cost.actual_cost:.4f}[/green]\n"
                f"[red]:x: Would cost ({cost.baseline_model or baseline_label}):  ${cost.would_have_cost:.4f}[/red]\n"
                f"{saved_line}\n"
                f"[cyan]:brain: Tokens:                     {cost.tokens_in} in / {cost.tokens_out} out ({total_tokens} total)[/cyan]\n"
                f"{badge}",
                title=":money_with_wings: Cost Analysis",
                border_style="green" if saved_something else "yellow",
                padding=(0, 1),
            )
        )
        console.print()

        hop = mh.hop_score.get_stats()
        score = hop["score"]
        if score >= 90:
            score_color, rating_emoji = "green", ":star:"
        elif score >= 70:
            score_color, rating_emoji = "yellow", ":thumbsup:"
        elif score >= 50:
            score_color, rating_emoji = "white", ":mega:"
        else:
            score_color, rating_emoji = "red", ":warning:"
        console.print("  :frog: [bold]Hop Score[/bold]")
        console.print(f"     Score   : [{score_color}]{score}/100[/{score_color}] {rating_emoji}")
        console.print(f"     Rating  : [{score_color}]{hop['rating']}[/{score_color}]")
        console.print(
            f"     Queries : [cyan]{hop['total_queries']}[/cyan] total, [cyan]{hop['optimal_routes']}[/cyan] optimal"
        )
        console.print()

        if verbose:
            explanation = mh.explain(result)
            console.print(
                Panel(explanation, title=":thought_balloon: Routing Rationale", border_style="cyan")
            )
            console.print()
            stats = mh.memory.get_overall_stats()
            perf_stats = mh.adaptive_threshold.get_stats()
            console.print(
                Panel(
                    f"[bold]Intelligence Stats[/bold]\n"
                    f"  Total experiences   : {stats['total']}\n"
                    f"  Avg quality         : {stats['avg_quality']:.2f}\n"
                    f"  Fallback rate       : {stats['fallback_rate']:.0%}\n"
                    f"  Confidence threshold: {perf_stats['threshold']:.3f}\n"
                    f"  Quality trend       : {perf_stats['trend']}\n"
                    f"  Hop Score           : {hop['score']}/100 ({hop['rating']})",
                    title=":brain: System Intelligence",
                    border_style="magenta",
                    padding=(0, 1),
                )
            )
            console.print()

        color = tier_color(result.tier)
        emoji = tier_emoji(result.tier)
        console.print(
            f"  :dart: Routed to [bold green]{result.model}[/bold green] [{color}]{emoji} {result.tier.upper()}[/{color}]"
        )
        if result.latency_ms < 500:
            lcolor, lrating = "green", ":rocket: Blazing fast!"
        elif result.latency_ms < 1000:
            lcolor, lrating = "yellow", ":thumbsup: Fast"
        else:
            lcolor, lrating = "white", ":clock1: Good"
        console.print(
            f"  :frog: Hopped in [bold {lcolor}]{result.latency_ms}ms[/bold {lcolor}]  {lrating}"
        )
        console.print()

    except Exception as e:
        error_msg = str(e)
        if json_output:
            print(json_mod.dumps({"error": error_msg}))  # noqa: T201 - raw JSON, no rich wrap
        else:
            console.print(Panel(f"[red]{error_msg}[/red]", title=":x: Error", border_style="red"))


def _short_error(error_msg: str) -> str:
    if "404" in error_msg and "model_not_found" in error_msg:
        return "model not found"
    if "429" in error_msg:
        return "rate limited or no credits"
    if "401" in error_msg or "authentication" in error_msg.lower():
        return "invalid API key"
    if "credit_balance_exhausted" in error_msg:
        return "no credits remaining"
    if len(error_msg) > 80:
        return error_msg[:80] + "..."
    return error_msg
