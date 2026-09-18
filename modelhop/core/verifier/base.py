"""Pluggable generic verifier framework (v1.1 W1)."""

from __future__ import annotations

from typing import List, Optional, Protocol

from ..models import VerifierResult


class Verifier(Protocol):
    name: str

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult: ...


class VerifierPipeline:
    """Ordered, short-circuit pipeline."""

    def __init__(self, verifiers: Optional[List] = None):
        self.verifiers: List = list(verifiers or [])

    def add(self, verifier) -> None:
        self.verifiers.append(verifier)

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        ctx = ctx or {}
        if not self.verifiers:
            return VerifierResult(verifier_name="pipeline", passed=True, score=1.0, details={})
        details: dict = {}
        for verifier in self.verifiers:
            try:
                result = verifier.verify(query, response, ctx)
            except Exception as exc:  # fail-closed on verifier crash
                return VerifierResult(
                    verifier_name=getattr(verifier, "name", "unknown"),
                    passed=False,
                    score=0.0,
                    details={"error": str(exc)},
                )
            details[result.verifier_name] = {"passed": result.passed, "score": result.score}
            if not result.passed:
                return VerifierResult(
                    verifier_name=result.verifier_name,
                    passed=False,
                    score=result.score,
                    details=details,
                )
        return VerifierResult(verifier_name="pipeline", passed=True, score=1.0, details=details)
