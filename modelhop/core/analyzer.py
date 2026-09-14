import json
import re
from typing import List

from ..core.models import ComplexityLevel, EmotionalTone, QueryAnalysis

ANALYSIS_PROMPT = """Analyze this user query and return a JSON object with the following fields:

{{
  "complexity": <float 0.0-1.0>,
  "level": "<simple|medium|complex>",
  "capabilities_needed": [<list of strings>],
  "emotional_tone": "<neutral|frustrated|urgent|angry>",
  "estimated_tokens": <int>,
  "reasoning": "<brief explanation>"
}}

Complexity guidelines:
- 0.0-0.3 (simple): FAQs, basic definitions, simple instructions, greetings
- 0.3-0.6 (medium): Explanations, comparisons, moderate analysis, multi-step instructions
- 0.6-1.0 (complex): Code generation, deep analysis, creative writing, multi-step reasoning, algorithms, data structures, system design

IMPORTANT: For coding/algorithm questions (including LeetCode-style problems, data structures, algorithms, debugging, code review), ALWAYS set complexity >= 0.7 and include "coding" in capabilities_needed.

Capabilities guidelines:
- faq: Answering frequently asked questions
- general: General conversation and information
- reasoning: Logical reasoning and analysis
- coding: Code generation, debugging, explanation, algorithms, data structures
- creative: Creative writing, brainstorming
- technical: Technical documentation, explanations
- classification: Categorizing or sorting information
- calculation: Mathematical computations

Query to analyze: {query}"""


class QueryAnalyzer:
    def __init__(self, providers: List):
        self.providers = providers
        self.cache: dict = {}

    @property
    def provider(self):
        return self.providers[0] if self.providers else None

    async def analyze(self, query: str) -> QueryAnalysis:
        cache_key = query.lower().strip()
        if cache_key in self.cache:
            return self.cache[cache_key]

        prompt = ANALYSIS_PROMPT.format(query=query)
        response = None

        for provider in self.providers:
            try:
                response = await provider.generate(
                    prompt,
                    max_tokens=200,
                    temperature=0.1
                )
                break
            except Exception:
                continue

        if response is None:
            return self._heuristic_analysis(query)

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            data = self._extract_json(response.content)

        analysis = QueryAnalysis(
            complexity=data.get("complexity", 0.5),
            level=ComplexityLevel(data.get("level", "medium")),
            capabilities_needed=data.get("capabilities_needed", ["general"]),
            emotional_tone=EmotionalTone(data.get("emotional_tone", "neutral")),
            estimated_tokens=data.get("estimated_tokens", 100),
            reasoning=data.get("reasoning", "")
        )

        self.cache[cache_key] = analysis
        return analysis

    def _heuristic_analysis(self, query: str) -> QueryAnalysis:
        query_lower = query.lower()
        complexity = 0.5
        level = ComplexityLevel.MEDIUM
        capabilities = ["general"]

        coding_terms = ["code", "function", "class", "algorithm", "data structure",
                        "debug", "implement", "write a program", "leetcode",
                        "array", "linked list", "tree", "graph", "sort", "search"]
        code_count = sum(1 for term in coding_terms if term in query_lower)

        algorithm_terms = ["o(n)", "o(1)", "o(log", "optimize", "efficient",
                           "time complexity", "space complexity", "dynamic programming",
                           "greedy", "recursion", "backtrack"]
        algo_count = sum(1 for term in algorithm_terms if term in query_lower)

        if code_count >= 2 or algo_count >= 1:
            complexity = 0.8
            level = ComplexityLevel.COMPLEX
            capabilities = ["coding", "reasoning"]
        elif code_count == 1:
            complexity = 0.7
            level = ComplexityLevel.COMPLEX
            capabilities = ["coding"]
        elif len(query) > 200:
            complexity = 0.6
            level = ComplexityLevel.COMPLEX

        return QueryAnalysis(
            complexity=complexity,
            level=level,
            capabilities_needed=capabilities,
            emotional_tone=EmotionalTone.NEUTRAL,
            estimated_tokens=len(query.split()) * 2,
            reasoning="Heuristic analysis (no provider available)"
        )

    def _extract_json(self, text: str) -> dict:
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {
            "complexity": 0.5,
            "level": "medium",
            "capabilities_needed": ["general"],
            "emotional_tone": "neutral",
            "estimated_tokens": 100,
            "reasoning": "Failed to parse analysis, using defaults"
        }
