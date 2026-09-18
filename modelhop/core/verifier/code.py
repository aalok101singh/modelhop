"""Optional example plugin: code verification (not the framework identity)."""

from __future__ import annotations

import ast

from ..models import VerifierResult


class CodeVerifier:
    name = "code"

    def verify(self, query: str, response: str, ctx: dict | None = None) -> VerifierResult:
        text = response or ""
        # Extract fenced python blocks if present.
        blocks = []
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            # Strip language tag line.
            lines = block.splitlines()
            if lines and lines[0].strip().lower() in ("python", "py"):
                lines = lines[1:]
            blocks.append("\n".join(lines))
        candidates = blocks or [text]
        for code in candidates:
            try:
                ast.parse(code)
                return VerifierResult(verifier_name=self.name, passed=True, score=1.0, details={})
            except SyntaxError:
                continue
        return VerifierResult(
            verifier_name=self.name,
            passed=False,
            score=0.0,
            details={"reason": "no parseable python block"},
        )
