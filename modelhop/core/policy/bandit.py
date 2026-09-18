"""Contextual bandit: Thompson sampling over discretized context (v1.1 W1)."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Dict, List, Optional

from ..models import ModelConfig


def _bucket_complexity(value: float) -> str:
    if value <= 0.3:
        return "simple"
    if value <= 0.6:
        return "medium"
    return "complex"


def context_key(query_type: str, complexity: float, tenant_tier: str) -> str:
    return f"{query_type}x{_bucket_complexity(float(complexity))}x{tenant_tier}"


class ContextualBandit:
    """Thompson sampling with Beta(success, fail) per (context, model).

    Optional LinUCB over feature vectors is available via select_linucb.
    Epsilon-floor exploration; priors seeded from performance/community.
    Persisted signed.
    """

    def __init__(self, epsilon: float = 0.05, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.epsilon = float(epsilon)
        self.alpha_prior = float(alpha_prior)
        self.beta_prior = float(beta_prior)
        # stats[context][model] = {"success": float, "trials": float, "reward_sum": float}
        self.stats: Dict[str, Dict[str, dict]] = defaultdict(dict)
        # LinUCB state: per-model A (dxd) and b (d).
        self._linucb: Dict[str, dict] = {}

    def seed_prior(self, model: str, ctx_key: str, quality: float, samples: int) -> None:
        cell = self.stats[ctx_key].setdefault(
            model, {"success": 0.0, "trials": 0.0, "reward_sum": 0.0}
        )
        # Convert quality+samples into pseudo-observations.
        cell["success"] += float(quality) * max(0, samples)
        cell["trials"] += max(0, samples)
        cell["reward_sum"] += float(quality) * max(0, samples)

    def select(
        self, candidates: List[ModelConfig], ctx, rng: Optional[random.Random] = None
    ) -> tuple[ModelConfig, float, dict]:

        assert candidates, "Bandit requires at least one candidate"
        rng = rng or random
        key = context_key(
            getattr(ctx, "query_type", "general"),
            float(getattr(ctx, "complexity", 0.5)),
            getattr(ctx, "tenant_tier", "default"),
        )
        penalties = getattr(ctx, "penalties", None) or {}
        # Epsilon-floor exploration.
        if rng.random() < self.epsilon:
            choice = rng.choice(candidates)
            return choice, 0.5, {"context": key, "explore": True, "method": "epsilon"}
        best = None
        best_score = -1.0
        info: dict = {"context": key, "explore": False, "method": "thompson"}
        for cand in candidates:
            cell = self.stats.get(key, {}).get(cand.name)
            if cell and cell["trials"] > 0:
                alpha = self.alpha_prior + cell["success"]
                beta = self.beta_prior + (cell["trials"] - cell["success"])
                sample = rng.betavariate(alpha, beta)
            else:
                # Unseen: optimistic prior sample.
                sample = rng.betavariate(self.alpha_prior, self.beta_prior)
            penalty = float((penalties or {}).get(cand.name, 0.0))
            score = sample - penalty
            if score > best_score:
                best_score = score
                best = cand
        assert best is not None
        info["score"] = float(best_score)
        return best, float(best_score), info

    def select_linucb(
        self, candidates: List[ModelConfig], features: List[float], alpha: float = 1.0
    ) -> tuple[ModelConfig, float, dict]:
        """Optional LinUCB over the feature vector."""

        d = len(features)
        best = None
        best_score = -1e18
        for cand in candidates:
            state = self._linucb.setdefault(
                cand.name,
                {
                    "A": [[1.0 if i == j else 0.0 for j in range(d)] for i in range(d)],
                    "b": [0.0] * d,
                },
            )
            # Solve A^{-1} b via naive Gauss (d is small, ~16).
            theta = _solve(state["A"], state["b"])
            mean = sum(t * f for t, f in zip(theta, features))
            # Confidence width from diagonal of inverse approx.
            inv_diag = _inv_diag(state["A"])
            width = alpha * math.sqrt(sum(inv_diag[i] * features[i] ** 2 for i in range(d)))
            score = mean + width
            if score > best_score:
                best_score = score
                best = cand
        assert best is not None
        return best, float(best_score), {"method": "linucb"}

    def update(self, model: ModelConfig, ctx, reward: float) -> None:
        key = context_key(
            getattr(ctx, "query_type", "general"),
            float(getattr(ctx, "complexity", 0.5)),
            getattr(ctx, "tenant_tier", "default"),
        )
        name = model.name if hasattr(model, "name") else str(model)
        cell = self.stats[key].setdefault(name, {"success": 0.0, "trials": 0.0, "reward_sum": 0.0})
        # Map reward (possibly negative) into [0,1] success mass via clipping.
        clipped = max(0.0, min(1.0, (float(reward) + 1.0) / 2.0))
        cell["success"] += clipped
        cell["trials"] += 1.0
        cell["reward_sum"] += float(reward)
        # LinUCB update if feature vector present.
        features = getattr(ctx, "features", None)
        if features:
            d = len(features)
            state = self._linucb.setdefault(
                name,
                {
                    "A": [[1.0 if i == j else 0.0 for j in range(d)] for i in range(d)],
                    "b": [0.0] * d,
                },
            )
            if len(state["b"]) != d:
                return
            for i in range(d):
                for j in range(d):
                    state["A"][i][j] += features[i] * features[j]
                state["b"][i] += float(reward) * features[i]

    def save(self, store, path: str = "modelhop_bandit.json") -> None:
        store.save(path, {"stats": {k: dict(v) for k, v in self.stats.items()}})

    @classmethod
    def load(cls, store, path: str = "modelhop_bandit.json") -> "ContextualBandit":
        from ..persistence import StateIntegrityError

        bandit = cls()
        try:
            data = store.load(path)
        except (StateIntegrityError, Exception):
            return bandit
        if isinstance(data, dict) and isinstance(data.get("stats"), dict):
            for k, v in data["stats"].items():
                if isinstance(v, dict):
                    bandit.stats[k] = dict(v)
        return bandit


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    M = [row[:] + [val] for row, val in zip(A, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[pivot] = M[pivot], M[col]
        denom = M[col][col] or 1e-9
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col] / denom
            for c in range(col, n + 1):
                M[r][c] -= factor * M[col][c]
    return [(M[i][n] / (M[i][i] or 1e-9)) for i in range(n)]


def _inv_diag(A: list[list[float]]) -> list[float]:
    n = len(A)
    out = []
    for i in range(n):
        out.append(1.0 / (abs(A[i][i]) or 1e-9))
    return out
