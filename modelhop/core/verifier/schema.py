from __future__ import annotations

import json
import re

from ..models import VerifierResult


class SchemaVerifier:
    """Format / JSON / regex checks."""

    name = "schema"

    def __init__(self, pattern: str | None = None, require_json: bool = False):
        self.pattern = re.compile(pattern) if pattern else None
        self.require_json = require_json

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        ctx = ctx or {}
        pattern = ctx.get("pattern") or self.pattern
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        require_json = ctx.get("require_json", self.require_json)
        if require_json:
            try:
                json.loads(response)
            except (json.JSONDecodeError, TypeError):
                return VerifierResult(
                    verifier_name=self.name,
                    passed=False,
                    score=0.0,
                    details={"reason": "invalid json"},
                )
        if pattern is not None and not pattern.search(response or ""):
            return VerifierResult(
                verifier_name=self.name,
                passed=False,
                score=0.0,
                details={"reason": "pattern mismatch"},
            )
        return VerifierResult(verifier_name=self.name, passed=True, score=1.0, details={})
