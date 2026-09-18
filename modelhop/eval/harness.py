"""Shadow -> canary -> rollout harness (v1.1 W4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class RolloutHarness:
    stages: List[str] = field(default_factory=lambda: ["shadow", "canary", "rollout"])
    canary_fraction: float = 0.05
    results: Dict[str, Any] = field(default_factory=dict)

    async def run(
        self,
        queries: List[str],
        baseline,
        candidate,
        metric: Callable[[Any], float] | None = None,
    ) -> Dict[str, Any]:
        import hashlib

        metric = metric or (
            lambda r: (
                float(
                    getattr(r, "confidence", {}).score
                    if hasattr(getattr(r, "confidence", {}), "score")
                    else 0.0
                )
                if hasattr(r, "confidence")
                else 0.0
            )
        )
        shadow_ok = 0
        canary_rewards: List[float] = []
        for q in queries:
            try:
                await baseline(q)
                cand_res = await candidate(q)
                shadow_ok += 1
                # Deterministic canary bucketing.
                bucket = (int(hashlib.sha256(q.encode()).hexdigest(), 16) % 100) / 100.0
                if bucket < self.canary_fraction:
                    try:
                        canary_rewards.append(metric(cand_res))
                    except Exception:
                        pass
            except Exception:
                continue
        avg_canary = sum(canary_rewards) / len(canary_rewards) if canary_rewards else 0.0
        self.results = {
            "shadow_ok": shadow_ok,
            "canary_n": len(canary_rewards),
            "canary_avg": avg_canary,
            "promote": shadow_ok == len(queries) and avg_canary >= 0.6,
        }
        return self.results
