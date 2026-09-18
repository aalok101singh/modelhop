"""Policy engine: hard constraints filter, soft constraints become penalties (v1.1 W1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from ..models import ModelConfig


@dataclass
class PolicyContext:
    query_type: str = "general"
    complexity: float = 0.5
    budget_remaining: Optional[float] = None
    cost_ceiling: Optional[float] = None
    latency_slo_ms: Optional[int] = None
    trust_required: dict = field(default_factory=dict)
    tenant_tier: str = "default"
    capabilities_needed: List[str] = field(default_factory=list)
    estimated_tokens_in: int = 100
    estimated_tokens_out: int = 500


@dataclass
class ConstraintResult:
    allowed: bool
    reason: str = ""
    penalty: float = 0.0


class Constraint(Protocol):
    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult: ...


@dataclass
class TrustConstraint:
    policy: dict = field(default_factory=dict)

    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        from ..trust import model_satisfies

        ok, reason = model_satisfies(candidate, ctx.trust_required, self.policy)
        return ConstraintResult(allowed=ok, reason=reason or "")


@dataclass
class BudgetConstraint:
    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        if ctx.cost_ceiling is None and ctx.budget_remaining is None:
            return ConstraintResult(allowed=True)
        est = (ctx.estimated_tokens_in / 1000) * candidate.cost_per_1k_input + (
            ctx.estimated_tokens_out / 1000
        ) * candidate.cost_per_1k_output
        if ctx.cost_ceiling is not None and est > ctx.cost_ceiling:
            return ConstraintResult(
                allowed=False, reason=f"Est cost {est:.4f} exceeds ceiling {ctx.cost_ceiling}"
            )
        if ctx.budget_remaining is not None and est > ctx.budget_remaining:
            return ConstraintResult(
                allowed=False, reason=f"Est cost {est:.4f} exceeds budget {ctx.budget_remaining}"
            )
        # Soft penalty proportional to spend.
        penalty = 0.0
        if ctx.cost_ceiling:
            penalty = est / ctx.cost_ceiling * 0.2
        return ConstraintResult(allowed=True, penalty=penalty)


@dataclass
class LatencySLOConstraint:
    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        if ctx.latency_slo_ms is None:
            return ConstraintResult(allowed=True)
        if candidate.avg_latency_ms > ctx.latency_slo_ms:
            return ConstraintResult(
                allowed=False,
                reason=f"Latency {candidate.avg_latency_ms}ms exceeds SLO {ctx.latency_slo_ms}ms",
            )
        return ConstraintResult(allowed=True)


@dataclass
class DataClassConstraint:
    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        required = (ctx.trust_required or {}).get("data_classes")
        if not required:
            return ConstraintResult(allowed=True)
        if isinstance(required, str):
            required = [required]
        model_dc = set(getattr(candidate.trust, "data_classes", ["general"]))
        missing = [d for d in required if d not in model_dc]
        if missing:
            return ConstraintResult(allowed=False, reason=f"Missing data classes {missing}")
        return ConstraintResult(allowed=True)


@dataclass
class ProviderHealthConstraint:
    health: object = None

    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        if self.health is None:
            return ConstraintResult(allowed=True)
        try:
            if hasattr(self.health, "allow") and not self.health.allow(candidate.name):
                return ConstraintResult(
                    allowed=False, reason=f"Provider {candidate.name} circuit open"
                )
        except Exception:
            return ConstraintResult(allowed=True)
        return ConstraintResult(allowed=True)


@dataclass
class CapabilityConstraint:
    def check(self, candidate: ModelConfig, ctx: PolicyContext) -> ConstraintResult:
        needed = [c for c in (ctx.capabilities_needed or []) if c != "general"]
        if not needed:
            return ConstraintResult(allowed=True)
        missing = [c for c in needed if c not in (candidate.capabilities or [])]
        if missing:
            return ConstraintResult(allowed=False, reason=f"Missing capabilities {missing}")
        return ConstraintResult(allowed=True)


@dataclass
class PolicyResult:
    eligible: List[ModelConfig]
    excluded: List[str]
    penalties: dict
    policy_version: str = "1"


class PolicyEngine:
    def __init__(self, constraints: Optional[List] = None, policy_version: str = "1"):
        self.constraints: List = list(constraints or [])
        self.policy_version = policy_version

    def evaluate(self, candidates: List[ModelConfig], ctx: PolicyContext) -> PolicyResult:
        eligible: List[ModelConfig] = []
        excluded: List[str] = []
        penalties: dict = {}
        for cand in candidates:
            ok = True
            total_penalty = 0.0
            for constraint in self.constraints:
                try:
                    res = constraint.check(cand, ctx)
                except Exception as exc:  # fail-closed on constraint errors
                    ok = False
                    excluded.append(f"{cand.name}: constraint error {exc}")
                    break
                if not res.allowed:
                    ok = False
                    excluded.append(f"{cand.name}: {res.reason}")
                    break
                total_penalty += float(res.penalty or 0.0)
            if ok:
                eligible.append(cand)
                penalties[cand.name] = total_penalty
        return PolicyResult(
            eligible=eligible,
            excluded=excluded,
            penalties=penalties,
            policy_version=self.policy_version,
        )


def default_engine(trust_policy: Optional[dict] = None, health=None) -> PolicyEngine:
    return PolicyEngine(
        constraints=[
            TrustConstraint(policy=dict(trust_policy or {})),
            CapabilityConstraint(),
            BudgetConstraint(),
            LatencySLOConstraint(),
            DataClassConstraint(),
            ProviderHealthConstraint(health=health),
        ]
    )
