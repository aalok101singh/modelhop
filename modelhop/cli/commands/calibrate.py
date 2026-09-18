import click
from rich.panel import Panel

from ..display import get_console

console = get_console()


@click.command("calibrate")
def calibrate() -> None:
    """:frog: Refit confidence calibration from labeled outcomes."""
    from modelhop import ModelHop
    from modelhop.core.reward import label_from_quality

    mh = ModelHop()
    pairs = []
    try:
        for exp in mh.memory.experiences[-500:]:
            pairs.append((float(exp.response_quality), label_from_quality(exp.response_quality)))
    except Exception:
        pass
    if len(pairs) < 10:
        console.print(
            Panel(f"Not enough labeled outcomes ({len(pairs)}/10).", title=":frog: Calibrate")
        )
        return
    mh.calibrator.fit(pairs)
    try:
        if mh._store is not None:
            mh.calibrator.save(mh._store)
    except Exception:
        pass
    try:
        ece = mh.calibrator.ece()
    except Exception:
        ece = 0.0
    console.print(
        Panel(f"Fitted on {len(pairs)} outcomes. ECE={ece:.3f}", title=":frog: Calibrate")
    )
