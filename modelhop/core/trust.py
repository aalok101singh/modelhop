"""Trust-policy hard-constraint filtering (v1.1 W3.9).

Permissive defaults: sparse metadata never blocks unless a strict
requirement is explicitly declared in policy or per-request context.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import ModelConfig

_SENSITIVITY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_SAFETY_ORDER = {"standard": 0, "elevated": 1, "high": 2}


class TrustViolation(Exception):
    pass


def _sensitivity_level(value: Optional[str]) -> int:
    if not value:
        return 0
    return _SENSITIVITY_ORDER.get(str(value).lower(), 0)


def _safety_level(value: Optional[str]) -> int:
    if not value:
        return 0
    return _SAFETY_ORDER.get(str(value).lower(), 0)


def model_satisfies(
    model: ModelConfig, requirement: Dict, policy: Optional[Dict] = None
) -> tuple[bool, Optional[str]]:
    """Check a single model against merged requirements. Returns (ok, reason)."""
    req = dict(policy or {})
    req.update(requirement or {})
    trust = model.trust

    # ZDR
    if req.get("require_zdr") and not trust.zdr:
        return False, f"{model.name} is not zero-data-retention"
    # Jurisdiction allowlist: enforced only when both sides declare.
    allowed = req.get("allowed_jurisdictions") or req.get("jurisdiction_allowlist")
    if allowed and trust.jurisdiction:
        if trust.jurisdiction not in allowed:
            return False, f"{model.name} jurisdiction {trust.jurisdiction} not allowed"
    # Sensitivity: model must handle at least the required level.
    required_sens = req.get("max_sensitivity") or req.get("sensitivity")
    if required_sens:
        if _sensitivity_level(trust.max_sensitivity) < _sensitivity_level(required_sens):
            return False, f"{model.name} max_sensitivity {trust.max_sensitivity} < {required_sens}"
    # Safety tier minimum.
    min_safety = req.get("min_safety_tier") or req.get("safety_tier")
    if min_safety:
        if _safety_level(trust.safety_tier) < _safety_level(min_safety):
            return False, f"{model.name} safety_tier {trust.safety_tier} < {min_safety}"
    # Data classes: required classes must be subset of model's.
    required_dc = req.get("data_classes") or req.get("required_data_classes")
    if required_dc:
        if isinstance(required_dc, str):
            required_dc = [required_dc]
        model_dc = set(trust.data_classes or ["general"])
        for dc in required_dc:
            if dc not in model_dc and "general" not in model_dc and dc != "general":
                # Permissive: if model declares only general, allow general queries.
                return False, f"{model.name} lacks data class {dc}"
    return True, None


def filter_by_trust(
    models: List[ModelConfig],
    policy: Optional[Dict] = None,
    requirement: Optional[Dict] = None,
) -> tuple[List[ModelConfig], List[str]]:
    """Hard-constraint filter. Returns (eligible, reasons_for_excluded)."""
    policy = policy or {}
    requirement = requirement or {}
    # Empty policy + empty requirement => everything eligible (permissive defaults).
    if not policy and not requirement:
        return list(models), []
    eligible: List[ModelConfig] = []
    excluded: List[str] = []
    for m in models:
        ok, reason = model_satisfies(m, requirement, policy)
        if ok:
            eligible.append(m)
        elif reason:
            excluded.append(reason)
    return eligible, excluded
