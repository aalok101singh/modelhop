import re
from typing import List

from .models import ComplexityLevel, QueryAnalysis, SubQuery

EXPLANATION_PATTERNS = [
    r'(?:explain|describe|what is|how does|how do|why does|why do|tell me about)\s+(.+?)(?:\s+and\s+|\s*$)',
    r'(.+?)\s+(?:and|also)\s+(?:explain|describe|tell me about)\s+(.+)',
]

CODE_PATTERNS = [
    r'(?:write|implement|create|build|code)\s+(?:a|an|the)\s+(.+?)(?:\s+and\s+|\s*$)',
    r'(.+?)\s+(?:and|also)\s+(?:write|implement|create|build|code)\s+(?:a|an|the)\s+(.+)',
]

AND_SPLIT = re.compile(
    r'\s+(?:and|also|additionally|plus|then)\s+',
    re.IGNORECASE
)


class QueryDecomposer:
    """Decomposes complex queries into sub-problems for independent routing."""

    def __init__(self):
        self._code_impl_pattern = re.compile(
            r'\b(?:write|implement|create|build|code|develop)\b',
            re.IGNORECASE
        )
        self._explain_pattern = re.compile(
            r'\b(?:explain|describe|what is|how does|how do|why|tell me about)\b',
            re.IGNORECASE
        )
        self._and_pattern = re.compile(
            r'\s+(?:and|also|additionally|plus|then)\s+',
            re.IGNORECASE
        )

    def decompose(
        self, query: str, analysis: QueryAnalysis
    ) -> List[SubQuery]:
        if analysis.complexity < 0.65:
            return [SubQuery(query=query, analysis=analysis, purpose="complete")]

        parts = self._split_query(query)

        if len(parts) <= 1:
            return [SubQuery(query=query, analysis=analysis, purpose="complete")]

        sub_queries = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            sub_analysis = self._analyze_sub_query(part)
            purpose = self._determine_purpose(part)
            sub_queries.append(SubQuery(
                query=part,
                analysis=sub_analysis,
                purpose=purpose,
            ))

        return sub_queries if sub_queries else [SubQuery(query=query, analysis=analysis, purpose="complete")]

    def _split_query(self, query: str) -> List[str]:
        splits = self._and_pattern.split(query)
        if len(splits) > 1:
            return splits

        comma_splits = query.split(", ")
        if len(comma_splits) > 1 and any(
            self._code_impl_pattern.search(p) or self._explain_pattern.search(p)
            for p in comma_splits
        ):
            return comma_splits

        return [query]

    def _analyze_sub_query(self, text: str) -> QueryAnalysis:
        text.lower()

        is_code = bool(self._code_impl_pattern.search(text))
        is_explain = bool(self._explain_pattern.search(text))

        if is_code and is_explain:
            return QueryAnalysis(
                complexity=0.7,
                level=ComplexityLevel.COMPLEX,
                capabilities_needed=["coding", "technical"],
            )
        elif is_code:
            return QueryAnalysis(
                complexity=0.75,
                level=ComplexityLevel.COMPLEX,
                capabilities_needed=["coding"],
            )
        elif is_explain:
            return QueryAnalysis(
                complexity=0.4,
                level=ComplexityLevel.MEDIUM,
                capabilities_needed=["technical"],
            )
        else:
            return QueryAnalysis(
                complexity=0.3,
                level=ComplexityLevel.MEDIUM,
                capabilities_needed=["general"],
            )

    def _determine_purpose(self, text: str) -> str:
        text_lower = text.lower()

        if self._code_impl_pattern.search(text):
            if "test" in text_lower:
                return "testing"
            if "debug" in text_lower or "fix" in text_lower:
                return "debugging"
            return "implementation"

        if self._explain_pattern.search(text):
            if "why" in text_lower:
                return "reasoning"
            if "how" in text_lower:
                return "explanation"
            return "description"

        return "general"

    def synthesize(self, sub_responses: list) -> str:
        if not sub_responses:
            return ""
        if len(sub_responses) == 1:
            return sub_responses[0].content if hasattr(sub_responses[0], 'content') else str(sub_responses[0])

        parts = []
        for sr in sub_responses:
            content = sr.content if hasattr(sr, 'content') else str(sr)
            parts.append(content)

        return "\n\n---\n\n".join(parts)
