from __future__ import annotations

from ..models import VerifierResult


class ConsistencyVerifier:
    """Self-consistency / cross-model agreement stub (lexical)."""

    name = "consistency"

    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        ctx = ctx or {}
        other = ctx.get("other_response", "")
        if not other:
            return VerifierResult(verifier_name=self.name, passed=True, score=1.0, details={})
        a = set((response or "").lower().split())
        b = set(other.lower().split())
        if not a or not b:
            return VerifierResult(verifier_name=self.name, passed=False, score=0.0, details={})
        jaccard = len(a & b) / len(a | b)
        return VerifierResult(
            verifier_name=self.name,
            passed=jaccard >= float(ctx.get("min_score", self.min_score)),
            score=float(jaccard),
            details={"jaccard": jaccard},
        )
