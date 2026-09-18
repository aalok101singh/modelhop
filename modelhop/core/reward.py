"""Calibrated reward model (v1.1 W1).

reward = w_q*quality - w_c*norm_cost - w_l*norm_latency
         + w_v*verifier_pass - w_f*fallback - w_r*retry
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RewardWeights:
    w_q: float = 1.0
    w_c: float = 0.3
    w_l: float = 0.2
    w_v: float = 0.4
    w_f: float = 0.3
    w_r: float = 0.1


DEFAULT_WEIGHTS = RewardWeights()


def compute_reward(
    quality: float,
    cost: float,
    latency_ms: int,
    verifier_pass: bool = True,
    fallback: bool = False,
    retries: int = 0,
    max_cost: float = 0.10,
    max_latency_ms: int = 5000,
    weights: RewardWeights | None = None,
) -> float:
    w = weights or DEFAULT_WEIGHTS
    norm_cost = min(1.0, max(0.0, cost / max_cost)) if max_cost > 0 else 0.0
    norm_lat = min(1.0, max(0.0, latency_ms / max_latency_ms)) if max_latency_ms > 0 else 0.0
    return (
        w.w_q * float(quality)
        - w.w_c * norm_cost
        - w.w_l * norm_lat
        + w.w_v * (1.0 if verifier_pass else 0.0)
        - w.w_f * (1.0 if fallback else 0.0)
        - w.w_r * float(retries)
    )


def label_from_quality(quality: float, threshold: float = 0.7) -> bool:
    return float(quality) >= float(threshold)
