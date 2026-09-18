from __future__ import annotations

import re

from ..models import VerifierResult


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


class GroundingVerifier:
    """Citation / context-overlap check."""

    name = "grounding"

    def __init__(self, min_overlap: float = 0.2):
        self.min_overlap = min_overlap

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        ctx = ctx or {}
        context = ctx.get("context", "")
        min_overlap = float(ctx.get("min_overlap", self.min_overlap))
        if not context:
            return VerifierResult(verifier_name=self.name, passed=True, score=1.0, details={})
        resp_toks = _tokens(response)
        ctx_toks = _tokens(context)
        if not resp_toks:
            return VerifierResult(
                verifier_name=self.name, passed=False, score=0.0, details={"reason": "empty"}
            )
        # Overlap of response tokens grounded in context.
        overlap = len(resp_toks & ctx_toks) / max(1, len(resp_toks))
        passed = overlap >= min_overlap
        return VerifierResult(
            verifier_name=self.name,
            passed=passed,
            score=float(overlap),
            details={"overlap": overlap},
        )
