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
        aux_responses = []
        if provider is not None:
            confidence_score, aux = await self._get_model_confidence(
                query, response.content, provider
            )
            if aux is not None:
                aux_responses.append(aux)
        else:
            confidence_score = self._heuristic_confidence(query, response, query_features)

        consensus_score = None
        consensus_model = None
        consensus_failure = None

        if self.enable_consensus and consensus_provider and confidence_score < self.threshold:
            consensus_score, consensus_model, consensus_failure, aux = await self._check_consensus(
                query, response, consensus_provider
            )
            aux_responses.extend(aux)

        if consensus_score is not None:
            final_score = (confidence_score + consensus_score) / 2
        else:
            final_score = confidence_score

        is_confident = final_score >= self.threshold
        reasoning = self._build_reasoning(
            final_score, is_confident, consensus_score, consensus_failure
        )

        return ConfidenceResult(
            score=final_score,
            is_confident=is_confident,
            threshold=self.threshold,
            consensus_model=consensus_model,
            consensus_score=consensus_score,
            reasoning=reasoning,
            auxiliary_responses=aux_responses,
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

    async def _get_model_confidence(self, query: str, response: str, provider=None):
        if provider is None:
            return 0.85, None

        prompt = CONFIDENCE_PROMPT.format(query=query, response=response)
        try:
            result = await provider.generate(prompt, max_tokens=100, temperature=0.1)
            data = self._extract_json(result.content)
            score = data.get("confidence", 0.85) if data else 0.85
            aux = result if isinstance(result, ProviderResponse) else None
            return score, aux
        except Exception:
            return 0.85, None

    async def _check_consensus(
        self, query: str, response: ProviderResponse, consensus_provider
    ) -> tuple:
        aux_responses = []
        try:
            consensus_response = await consensus_provider.generate(query, max_tokens=500)
            if isinstance(consensus_response, ProviderResponse):
                aux_responses.append(consensus_response)
            prompt = CONSENSUS_PROMPT.format(
                query=query, response_a=response.content, response_b=consensus_response.content
            )
            judge_result = await consensus_provider.generate(
                prompt, max_tokens=100, temperature=0.1
            )
            if isinstance(judge_result, ProviderResponse):
                aux_responses.append(judge_result)
            data = self._extract_json(judge_result.content)
            if data is None or "similarity" not in data:
                return None, None, "Consensus response could not be parsed", aux_responses
            similarity = data["similarity"]
            consensus_model = (
                consensus_response.model_used
                if isinstance(consensus_response, ProviderResponse)
                else None
            )
            return similarity, consensus_model, None, aux_responses
        except Exception as exc:
            return None, None, f"Consensus check failed: {exc}", aux_responses

    def _extract_json(self, text: str) -> Optional[dict]:
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _build_reasoning(
        self,
        score: float,
        is_confident: bool,
        consensus_score: Optional[float],
        consensus_failure: Optional[str] = None,
    ) -> str:
        if is_confident:
            base = f"Response is confident (score: {score:.2f})"
        else:
            base = f"Response is not confident (score: {score:.2f})"

        if consensus_score is not None:
            base += f" | Cross-model consensus: {consensus_score:.2f}"
        elif consensus_failure is not None:
            base += f" | Consensus unavailable: {consensus_failure}"

        return base
