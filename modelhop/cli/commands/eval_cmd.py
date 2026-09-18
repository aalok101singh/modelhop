import asyncio
import json as json_mod

import click
from rich.panel import Panel

from ..display import get_console

console = get_console()


@click.group(invoke_without_command=True)
@click.pass_context
def eval(ctx) -> None:
    """:frog: Offline evaluation and rollout harness."""
    if ctx.invoked_subcommand is None:
        console.print("Use: modelhop eval offline | modelhop eval drift")


@eval.command("offline")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def offline(json_output: bool) -> None:
    """IPS / doubly-robust counterfactual estimate from the ledger."""
    asyncio.run(_offline_async(json_output))


async def _offline_async(json_output: bool) -> None:
    from modelhop import ModelHop
    from modelhop.eval.offline import doubly_robust, ips_estimate

    mh = ModelHop()
    logged = []
    try:
        for payload in mh.ledger.replay():
            logged.append(
                {
                    "reward": float(payload.get("confidence", 0.0)),
                    "propensity": 1.0,
                    "model": payload.get("model", ""),
                }
            )
    except Exception:
        pass
    ips = ips_estimate(logged, lambda row: 1.0)
    dr = doubly_robust(logged, lambda row: 1.0, lambda row: float(row.get("reward", 0.0)))
    if json_output:
        print(
            json_mod.dumps({"n": len(logged), "ips": ips, "doubly_robust": dr}, indent=2)
        )  # noqa: T201
    else:
        console.print(
            Panel(
                f"Logged: {len(logged)}\nIPS: {ips:.3f}\nDoubly-robust: {dr:.3f}",
                title=":frog: Offline Eval",
            )
        )


@eval.command("drift")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def drift(json_output: bool) -> None:
    """Feature/reward drift check with auto-rollback signal."""
    from modelhop import ModelHop
    from modelhop.eval.drift import DriftDetector

    mh = ModelHop()
    det = DriftDetector()
    try:
        payloads = list(mh.ledger.replay())
        for p in payloads[:50]:
            det.add_baseline(float(p.get("confidence", 0.7)))
        status = "stable"
        for p in payloads[50:]:
            status = det.add(float(p.get("confidence", 0.7)))
    except Exception as exc:
        status = f"error: {exc}"
    if json_output:
        print(
            json_mod.dumps({"status": status, "rolled_back": det.rolled_back}, indent=2)
        )  # noqa: T201
    else:
        console.print(Panel(f"Status: {status}", title=":frog: Drift"))
