from __future__ import annotations

from ..models import VerifierResult


class CustomVerifier:
    """User-registered callable: fn(query, response, ctx) -> bool|tuple|VerifierResult."""

    name = "custom"

    def __init__(self, fn, name: str = "custom"):
        self.fn = fn
        self.name = name

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        out = self.fn(query, response, ctx or {})
        if isinstance(out, VerifierResult):
            return out
        if isinstance(out, tuple):
            passed, score = out[0], float(out[1]) if len(out) > 1 else (bool(out[0]), 1.0)
            return VerifierResult(verifier_name=self.name, passed=bool(passed), score=score)
        return VerifierResult(verifier_name=self.name, passed=bool(out), score=1.0 if out else 0.0)
