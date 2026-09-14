import json
import re
from typing import Optional

from .models import ConfidenceResult, ProviderResponse, QueryFeatures

CONFIDENCE_PROMPT = """Rate your confidence in this response on a scale of 0.0 to 1.0.

Query: {query}

Your Response: {response}

Return ONLY a JSON object:
{{"confidence": <float 0.0-1.0>, "reasoning": "<brief explanation>"}}

Confidence guidelines:
- 0.9-1.0: Very confident, direct answer, no ambiguity
- 0.7-0.9: Confident, answer is correct but may have minor gaps
- 0.5-0.7: Somewhat confident, answer is approximate or incomplete
- 0.3-0.5: Not confident, answer may be incorrect
- 0.0-0.3: Very uncertain, likely incorrect"""

CONSENSUS_PROMPT = """Compare these two responses to the same query and determine if they agree.

Query: {query}

Response A: {response_a}

Response B: {response_b}

Return ONLY a JSON object:
{{"similarity": <float 0.0-1.0>, "agree": <true|false>, "reasoning": "<brief explanation>"}}

Similarity guidelines:
- 0.9-1.0: Nearly identical answers
- 0.7-0.9: Similar answers, minor differences
- 0.5-0.7: Partially overlapping answers
- 0.3-0.5: Different answers but both plausible
- 0.0-0.3: Completely different or contradictory answers"""


class ConfidenceEngine:
    def __init__(self, threshold: float = 0.7, enable_consensus: bool = True):
        self.threshold = threshold
        self.enable_consensus = enable_consensus

    async def check(
        self,
        query: str,
        response: ProviderResponse,
        provider=None,
        consensus_provider=None,
        query_features: Optional[QueryFeatures] = None,
    ) -> ConfidenceResult:
        if provider is not None:
            confidence_score = await self._get_model_confidence(query, response.content, provider)
        else:
            confidence_score = self._heuristic_confidence(query, response, query_features)

        consensus_score = None
        consensus_model = None

        if self.enable_consensus and consensus_provider and confidence_score < self.threshold:
            consensus_score, consensus_model = await self._check_consensus(
                query, response, consensus_provider
            )

        if consensus_score is not None:
            final_score = (confidence_score + consensus_score) / 2
        else:
            final_score = confidence_score

        is_confident = final_score >= self.threshold
        reasoning = self._build_reasoning(final_score, is_confident, consensus_score)

        return ConfidenceResult(
            score=final_score,
            is_confident=is_confident,
            threshold=self.threshold,
            consensus_model=consensus_model,
            consensus_score=consensus_score,
            reasoning=reasoning,
        )

    def _heuristic_confidence(
        self,
        query: str,
        response: ProviderResponse,
        query_features: Optional[QueryFeatures] = None,
    ) -> float:
        score = 0.75

        content = response.content or ""
        content_len = len(content)

        if content_len < 50:
            score -= 0.2
        elif content_len > 500:
            score += 0.05

        if response.tokens_out and response.tokens_out > 0:
            if response.tokens_out < 20:
                score -= 0.15

        if "i don't know" in content.lower() or "i cannot" in content.lower():
            score -= 0.25
        if "error" in content.lower() and content_len < 100:
            score -= 0.2

        if query_features:
            if query_features.code_keyword_count >= 2:
                has_code = "```" in content or "def " in content or "function " in content
                if has_code:
                    score += 0.05
                else:
                    score -= 0.1

            if query_features.is_debugging:
                if "fix" in content.lower() or "solution" in content.lower():
                    score += 0.05

        return max(0.3, min(0.95, score))

    async def _get_model_confidence(self, query: str, response: str, provider=None) -> float:
        if provider is None:
            return 0.85

        prompt = CONFIDENCE_PROMPT.format(query=query, response=response)
        try:
            result = await provider.generate(prompt, max_tokens=100, temperature=0.1)
            data = self._extract_json(result.content)
            return data.get("confidence", 0.85)
        except Exception:
            return 0.85

    async def _check_consensus(
        self, query: str, response: ProviderResponse, consensus_provider
    ) -> tuple:
        try:
            consensus_response = await consensus_provider.generate(query, max_tokens=500)
            prompt = CONSENSUS_PROMPT.format(
                query=query, response_a=response.content, response_b=consensus_response.content
            )
            judge_result = await consensus_provider.generate(
                prompt, max_tokens=100, temperature=0.1
            )
            data = self._extract_json(judge_result.content)
            similarity = data.get("similarity", 0.88)
            return similarity, consensus_response.model_used
        except Exception:
            return 0.88, None

    def _extract_json(self, text: str) -> dict:
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {"confidence": 0.85, "reasoning": "Failed to parse"}

    def _build_reasoning(
        self, score: float, is_confident: bool, consensus_score: Optional[float]
    ) -> str:
        if is_confident:
            base = f"Response is confident (score: {score:.2f})"
        else:
            base = f"Response is not confident (score: {score:.2f})"

        if consensus_score is not None:
            base += f" | Cross-model consensus: {consensus_score:.2f}"

        return base
