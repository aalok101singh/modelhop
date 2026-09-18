"""Offline counterfactual evaluation: IPS / doubly-robust (v1.1 W4)."""

from __future__ import annotations

from typing import List


def _behavior_propensity(row: dict) -> float | None:
    """Propensity of the logging policy. None when absent or without support.

    Missing propensity must exclude the row rather than fabricate certainty.
    """
    if "propensity" not in row or row.get("propensity") is None:
        return None
    try:
        pi_b = float(row["propensity"])
    except (TypeError, ValueError):
        return None
    if pi_b <= 0:
        return None
    return pi_b


def ips_estimate(logged: List[dict], target_policy) -> float:
    """Inverse-propensity scoring: mean(r * pi_e / pi_b).

    Rows with zero/negative propensity (no support) are excluded.
    """
    total = 0.0
    n = 0
    for row in logged:
        reward = float(row.get("reward", 0.0))
        pi_b = _behavior_propensity(row)
        if pi_b is None:
            continue
        try:
            pi_e = float(target_policy(row))
        except Exception:
            pi_e = 0.0
        total += reward * (pi_e / pi_b)
        n += 1
    return total / n if n else 0.0


def doubly_robust(logged: List[dict], target_policy, reward_model) -> float:
    """Doubly-robust: mean(q + (r - q) * pi_e / pi_b).

    Rows with zero/negative propensity (no support) are excluded.
    """
    total = 0.0
    n = 0
    for row in logged:
        reward = float(row.get("reward", 0.0))
        pi_b = _behavior_propensity(row)
        if pi_b is None:
            continue
        try:
            pi_e = float(target_policy(row))
        except Exception:
            pi_e = 0.0
        try:
            q = float(reward_model(row))
        except Exception:
            q = 0.0
        total += q + (reward - q) * (pi_e / pi_b)
        n += 1
    return total / n if n else 0.0
