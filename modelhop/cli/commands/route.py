import asyncio

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


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
        console.print(Panel(
            "[bold red]:x: No API keys found![/bold red]\n\n"
            "Set at least one environment variable:\n"
            "  [cyan]$env:GROQ_API_KEY=your-key[/cyan]\n"
            "  [cyan]$env:GEMINI_API_KEY=your-key[/cyan]\n"
            "  [cyan]$env:OPENAI_API_KEY=your-key[/cyan]",
            title=":warning: Configuration Error",
            border_style="red",
        ))
        console.print()
        return

    if not mh.analyzer.providers:
        console.print()
        console.print(Panel(
            "[bold red]:x: No provider for query analysis![/bold red]\n\n"
            "Set at least one API key:\n"
            "  [cyan]$env:GROQ_API_KEY=your-key[/cyan]\n"
            "  [cyan]$env:GEMINI_API_KEY=your-key[/cyan]\n"
            "  [cyan]$env:OPENAI_API_KEY=your-key[/cyan]",
            title=":warning: Configuration Error",
            border_style="red",
        ))
        console.print()
        return

    if not json_output:
        console.print()
        console.print(Panel(
            "[bold green]:frog: ModelHop v1.0.0[/bold green]\n"
            "[dim]Intelligent routing with multi-signal analysis & experience learning[/dim]",
            border_style="green",
            padding=(0, 2),
        ))
        console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("  :mag: Extracting features...", total=None)
            query_features = mh.feature_extractor.extract(query)
            progress.update(task, completed=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("  :brain: Analyzing query...", total=None)
            analysis = await mh.analyzer.analyze(query)
            progress.update(task, completed=True)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("  :dart: Learning routing decision...", total=None)
            if force_model:
                decision = mh.router.route_with_model(force_model, analysis)
                reasoning = f"Forced model selection: {force_model}"
            else:
                decision, reasoning = mh.learning_router.route(analysis, query_features)
            progress.update(task, completed=True)

        if not json_output:
            console.print("  :mag: [bold]Feature Extraction[/bold]")
            console.print(f"     Query Type     : [cyan]{query_features.query_type.value}[/cyan]")
            console.print(f"     Code Keywords  : {query_features.code_keyword_count}")
            console.print(f"     Algorithm Terms: {query_features.algorithm_term_count}")
            if query_features.has_constraints:
                console.print("     Constraints    : [yellow]detected[/yellow]")
            if query_features.requires_optimization:
                console.print("     Optimization   : [yellow]required[/yellow]")
            console.print()

            console.print("  :brain: [bold]AI Analysis[/bold]")
            console.print(f"     Base Complexity : [cyan]{analysis.complexity:.2f}[/cyan]")
            console.print(f"     Capabilities   : {', '.join(analysis.capabilities_needed)}")
            if analysis.emotional_tone.value != "neutral":
                console.print(f"     Tone : [yellow]{analysis.emotional_tone.value}[/yellow]")
            console.print()

            similar = mh.memory.find_similar(query_features, top_k=3, min_similarity=0.4)
            if similar:
                console.print("  :books: [bold]Experience Memory[/bold]")
                console.print(f"     Similar queries found : [cyan]{len(similar)}[/cyan]")
                avg_q = sum(e.response_quality for e in similar) / len(similar)
                console.print(f"     Avg historical quality: [cyan]{avg_q:.2f}[/cyan]")
                models_seen = set(e.model_name for e in similar)
                console.print(f"     Models tried          : {', '.join(models_seen)}")
                console.print()

            tier_colors = {"free": "green", "mid": "yellow", "premium": "red"}
            tier_emoji = {"free": ":free:", "mid": ":warning:", "premium": ":crown:"}
            color = tier_colors.get(decision.tier.value, "white")
            emoji = tier_emoji.get(decision.tier.value, "")
            console.print("  :dart: [bold]Routing Decision[/bold]")
            console.print(f"     Model : [bold green]{decision.model.name}[/bold green]")
            console.print(f"     Tier  : [{color}]{emoji} {decision.tier.value.upper()}[/{color}]")
            console.print(f"     Reason: {decision.reason}")
            if reasoning:
                console.print(f"     Logic : {reasoning}")
            console.print()

        response = None
        provider = None
        fallback_count = 0
        tried_models = set()
        original_decision = decision

        while fallback_count < 4:
            model_name = decision.model.name
            tried_models.add(model_name)

            provider = mh.registry.get_provider(model_name)
            if provider is None:
                if not json_output:
                    console.print(f"  :warning: [yellow]Provider not available for {model_name}, trying next...[/yellow]")
                next_decision = _get_next_fallback(mh, decision, tried_models)
                if next_decision is None:
                    break
                decision = next_decision
                fallback_count += 1
                continue

            try:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True
                ) as progress:
                    task = progress.add_task("  :zap: Generating response...", total=None)
                    response = await provider.generate(query)
                    progress.update(task, completed=True)
                break
            except Exception as e:
                error_msg = str(e)
                if not json_output:
                    console.print(f"  :warning: [yellow]{model_name} failed: {_short_error(error_msg)}[/yellow]")
                    console.print("  :arrow_right: [dim]Falling back to next model...[/dim]")
                next_decision = _get_next_fallback(mh, decision, tried_models)
                if next_decision is None:
                    break
                decision = next_decision
                fallback_count += 1

        if response is None:
            if json_output:
                console.print('{"error": "All models failed"}')
            else:
                console.print(Panel(
                    "[bold red]:x: All models failed![/bold red]\n\n"
                    "No provider could handle this query.\n"
                    "Check your API keys and model configuration.",
                    title=":warning: Routing Failed",
                    border_style="red",
                ))
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("  :mag: Checking confidence...", total=None)
            consensus_provider = _get_consensus_provider(mh, decision.model.name)
            confidence = await mh.confidence_engine.check(
                query, response, provider, consensus_provider, query_features
            )
            progress.update(task, completed=True)

        conf_fallback_count = 0
        while not confidence.is_confident and conf_fallback_count < 3:
            fallback_decision = await mh.fallback.handle_low_confidence(
                query, analysis, decision.model, confidence
            )
            if fallback_decision is None:
                break

            decision = fallback_decision
            fallback_provider = mh.registry.get_provider(decision.model.name)
            if fallback_provider is None:
                break
            provider = fallback_provider
            try:
                response = await provider.generate(query)
            except Exception:
                break
            confidence = await mh.confidence_engine.check(
                query, response, provider, query_features=query_features
            )
            conf_fallback_count += 1

        mh.memory.record(
            query=query,
            query_features=query_features,
            analysis=analysis,
            decision=decision,
            response_quality=confidence.score,
            fallback_used=fallback_count > 0 or conf_fallback_count > 0,
            latency_ms=response.latency_ms,
        )
        mh.performance.record_outcome(
            model_name=decision.model.name,
            query_type=query_features.query_type,
            quality=confidence.score,
            latency_ms=response.latency_ms,
            fallback_used=fallback_count > 0 or conf_fallback_count > 0,
        )
        mh.adaptive_threshold.adjust(confidence.score)

        cost = mh.cost_tracker.calculate(response, decision.model)

        trace = mh.trace_logger.log(
            query=query,
            analysis=analysis,
            decision=decision,
            response=response,
            confidence=confidence,
            cost=cost,
            fallback_count=fallback_count + conf_fallback_count
        )

        mh.shield.check_quality(trace)
        mh.hop_score.update(confidence.is_confident)

        if fallback_count > 0 and not json_output:
            console.print(f"  :recycle: [yellow]Fell back from {original_decision.model.name} to {decision.model.name}[/yellow]")
            console.print()

        if json_output:
            import json
            output = {
                "query": query,
                "features": {
                    "query_type": query_features.query_type.value,
                    "code_keywords": query_features.code_keyword_count,
                    "algorithm_terms": query_features.algorithm_term_count,
                    "has_constraints": query_features.has_constraints,
                },
                "complexity": analysis.complexity,
                "model": decision.model.name,
                "tier": decision.tier.value,
                "reasoning": reasoning,
                "response": response.content,
                "confidence": confidence.score,
                "cost": cost.actual_cost,
                "savings": cost.savings,
                "latency_ms": response.latency_ms,
                "fallback_count": fallback_count + conf_fallback_count,
                "hop_score": mh.hop_score.get_stats(),
            }
            console.print(json.dumps(output, indent=2))
        else:
            console.print(Panel(
                response.content,
                title=":bulb: Response",
                border_style="cyan",
                padding=(0, 1),
            ))
            console.print()

            savings_pct = cost.savings_percentage
            if savings_pct >= 90:
                badge = "[bold green]:tada: AMAZING SAVINGS[/bold green]"
            elif savings_pct >= 50:
                badge = "[bold yellow]:heavy_check_mark: GREAT SAVINGS[/bold yellow]"
            else:
                badge = "[dim]Some savings[/dim]"

            console.print(Panel(
                f"[green]:moneybag: Actual cost:          ${cost.actual_cost:.4f}[/green]\n"
                f"[red]:x: Would cost (GPT-4):  ${cost.would_have_cost:.4f}[/red]\n"
                f"[bold green]:sparkles: You saved:            ${cost.savings:.4f} ({cost.savings_percentage:.0f}%)[/bold green]\n"
                f"{badge}",
                title=":money_with_wings: Cost Analysis",
                border_style="yellow",
                padding=(0, 1),
            ))
            console.print()

            hop = mh.hop_score.get_stats()
            score = hop["score"]
            if score >= 90:
                score_color = "green"
                rating_emoji = ":star:"
            elif score >= 70:
                score_color = "yellow"
                rating_emoji = ":thumbsup:"
            elif score >= 50:
                score_color = "white"
                rating_emoji = ":mega:"
            else:
                score_color = "red"
                rating_emoji = ":warning:"
            console.print("  :frog: [bold]Hop Score[/bold]")
            console.print(f"     Score   : [{score_color}]{score}/100[/{score_color}] {rating_emoji}")
            console.print(f"     Rating  : [{score_color}]{hop['rating']}[/{score_color}]")
            console.print(f"     Queries : [cyan]{hop['total_queries']}[/cyan] total, [cyan]{hop['optimal_routes']}[/cyan] optimal")
            console.print()

            if verbose:
                stats = mh.memory.get_overall_stats()
                perf_stats = mh.adaptive_threshold.get_stats()
                hop = mh.hop_score.get_stats()
                console.print(Panel(
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
                ))
                console.print()

            if response.latency_ms < 500:
                lcolor = "green"
                lrating = ":rocket: Blazing fast!"
            elif response.latency_ms < 1000:
                lcolor = "yellow"
                lrating = ":thumbsup: Fast"
            else:
                lcolor = "white"
                lrating = ":clock1: Good"
            console.print(f"  :frog: Hopped in [bold {lcolor}]{response.latency_ms}ms[/bold {lcolor}]  {lrating}")
            console.print()

    except Exception as e:
        error_msg = str(e)
        if json_output:
            import json
            console.print(json.dumps({"error": error_msg}))
        else:
            console.print(Panel(
                f"[red]{error_msg}[/red]",
                title=":x: Error",
                border_style="red",
            ))


def _get_next_fallback(mh, current_decision, tried_models):
    available = mh.registry.get_available_providers()
    for name, provider in available.items():
        if name not in tried_models and name != current_decision.model.name:
            model = mh.registry.get_model(name)
            if model:
                from modelhop.core.models import RoutingDecision
                return RoutingDecision(
                    model=model,
                    tier=model.tier,
                    reason=f"Fallback from {current_decision.model.name} (unavailable)",
                    alternatives=[],
                )
    return None


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


def _get_consensus_provider(mh, exclude_model: str):
    for name, provider in mh.registry.get_available_providers().items():
        if name != exclude_model:
            return provider
    return None
