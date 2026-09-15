"""
Example: custom_agent — build your own decision loop on top of ModelHop.

A minimal "research agent" that uses the SDK as its routing brain:
extract local signals, inspect the LearningRouter's decision and
reasoning, generate the answer, and render a plain-English explanation
of why that model was chosen.

Run:
    python examples/custom_agent.py
"""

import asyncio

from rich.console import Console
from rich.panel import Panel

from modelhop import ModelHop

console = Console()

PROMPTS = [
    "Explain what a database index is and when you would use one.",
    "Write a function that detects a cycle in a linked list using constant space.",
]


async def main() -> None:
    mh = ModelHop()

    if not mh.registry.get_available_providers():
        console.print(
            Panel(
                "[bold red]No API keys found.[/bold red]\n\n"
                "Set at least one of GROQ_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY "
                "before running this example.",
                title=":warning: Configuration Error",
                border_style="red",
            )
        )
        return

    for prompt in PROMPTS:
        features = mh.feature_extractor.extract(prompt)
        analysis = await mh.analyzer.analyze(prompt)
        decision, reasoning = mh.learning_router.route(analysis, features)

        console.print(Panel(f"[bold]Request:[/bold] {prompt}", border_style="dim"))
        console.print(f"  :mag: Query type        : {features.query_type.value}")
        console.print(
            f"  :brain: Complexity       : {analysis.complexity:.2f} ({analysis.level.value})"
        )
        console.print("  :dart: Capabilities     : " + ", ".join(analysis.capabilities_needed))
        console.print(f"  :frog: Routed to        : {decision.model.name} ({decision.tier.value})")
        console.print(f"  :clipboard: Router logic      : {reasoning}")
        console.print()

        explanation = mh.reasoning_engine.explain(
            query=prompt,
            analysis=analysis,
            decision=decision,
            query_features=features,
            merged_reasoning=reasoning,
        )
        console.print(
            Panel(explanation, title=":thought_balloon: Why this model", border_style="magenta")
        )
        console.print()

        try:
            response = await mh.route(prompt)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/red]", title=":x: Route Failed", border_style="red"))
            console.print()
            continue

        console.print(Panel(response.content, title=":bulb: Answer", border_style="cyan"))
        model = mh.registry.get_model(response.model_used)
        if model is not None:
            cost = mh.cost_tracker.calculate(response, model)
            console.print(
                f"  :moneybag: ${cost.actual_cost:.4f} actual vs "
                f"${cost.would_have_cost:.4f} GPT-4  "
                f"({cost.savings_percentage:.0f}% saved)  "
                f"in {response.latency_ms}ms"
            )
        console.print()

    hop = mh.hop_score.get_stats()
    console.print(f"  :frog: [bold]Hop Score:[/bold] {hop['score']}/100 ({hop['rating']})")


if __name__ == "__main__":
    asyncio.run(main())
