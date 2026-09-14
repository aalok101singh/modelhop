import math
import re
from typing import Dict, List, Set

from .models import QueryFeatures, QueryType

CODE_KEYWORDS: Set[str] = {
    "function", "class", "method", "implement", "write", "code", "program",
    "algorithm", "array", "list", "dictionary", "hash", "stack", "queue",
    "tree", "graph", "node", "loop", "recursion", "iterate", "sort", "search",
    "binary", "traverse", "insert", "delete", "update", "return", "variable",
    "compile", "runtime", "debug", "syntax", "int", "string", "boolean",
    "float", "void", "null", "true", "false", "if", "else", "for", "while",
    "switch", "case", "break", "continue", "try", "catch", "throw", "import",
    "export", "module", "package", "struct", "enum", "interface", "type",
    "async", "await", "promise", "callback", "closure", "lambda", "def",
    "print", "input", "read", "open", "close", "file", "stream",
    "duplicate", "element", "index", "value", "pointer", "reference",
    "iterate", "traverse", "recursive", "iterative", "inplace", "in-place",
    "subarray", "subsequence", "substring", "permutation", "combination",
    "fibonacci", "factorial", "palindrome", "anagram", "bracket",
}

ALGORITHM_KEYWORDS: Set[str] = {
    "sort", "search", "merge", "quick", "heap", "bubble", "insertion",
    "selection", "linear", "binary", "bfs", "dfs", "dijkstra", "bellman",
    "floyd", "warshall", "kruskal", "prim", "huffman", "knapsack",
    "dynamic", "programming", "recursion", "memoization", "backtracking",
    "greedy", "divide", "conquer", "sliding", "window", "two", "pointer",
    "fast", "slow", "pointer", "cycle", "detect", "linked", "list",
    "binary", "search", "tree", "bst", "avl", "red", "black", "trie",
    "hash", "map", "set", "heap", "priority", "queue", "stack", "deque",
    "graph", "vertex", "edge", "adjacency", "matrix", "list", "directed",
    "undirected", "weighted", "shortest", "path", "minimum", "spanning",
    "tree", "topological", "sort", "strongly", "connected", "component",
}

COMPLEXITY_KEYWORDS: Set[str] = {
    "optimize", "efficient", "scalable", "performance", "latency", "throughput",
    "complexity", "time", "space", "o(n)", "o(1)", "o(log", "o(n^2)",
    "amortized", "worst", "case", "best", "average", "in", "place",
    "without", "extra", "space", "constant", "loglinear", "quadratic",
    "exponential", "polynomial", "linear", "sublinear", "parallel",
    "concurrent", "distributed", "cache", "memory", "disk", "network",
    "io", "bottleneck", "tradeoff", "trade", "off", "balance",
}

TECHNICAL_TERMS: Set[str] = {
    "api", "sdk", "database", "sql", "nosql", "redis", "mysql", "postgres",
    "mongodb", "server", "client", "http", "https", "tcp", "udp", "ip",
    "dns", "ssl", "tls", "encryption", "authentication", "authorization",
    "oauth", "jwt", "token", "session", "cookie", "cache", "proxy",
    "load", "balancer", "nginx", "apache", "docker", "kubernetes", "aws",
    "azure", "gcp", "cloud", "microservice", "monolith", "rest", "graphql",
    "grpc", "websocket", "queue", "pub", "sub", "message", "broker",
    "kafka", "rabbitmq", "elasticsearch", "kibana", "monitoring",
    "logging", "metrics", "tracing", "ci", "cd", "pipeline", "git",
    "repository", "branch", "merge", "commit", "pull", "request",
}

DEBUG_KEYWORDS: Set[str] = {
    "fix", "error", "bug", "broken", "not", "working", "fails", "crash",
    "exception", "traceback", "stack", "overflow", "null", "pointer",
    "undefined", "reference", "type", "mismatch", "segfault", "deadlock",
    "race", "condition", "memory", "leak", "infinite", "loop", "hang",
    "timeout", "disconnect", "refused", "invalid", "unexpected",
}

CREATIVE_KEYWORDS: Set[str] = {
    "write", "story", "poem", "creative", "brainstorm", "idea", "imagine",
    "fiction", "narrative", "character", "plot", "dialogue", "essay",
    "article", "blog", "content", "copy", "marketing", "slogan", "tagline",
    "name", "brand", "design", "logo", "visual", "art", "draw", "paint",
    "compose", "music", "song", "lyric", "script", "screenplay", "novel",
}


class FeatureExtractor:
    """Extracts multi-signal features from queries without any API calls."""

    def __init__(self):
        self._code_pattern = re.compile(
            r'(?:def|class|function|import|from|return|if|else|for|while|'
            r'\{| \}|\[|\]|=>|->|\#\s*include|public|private|static)',
            re.IGNORECASE
        )
        self._constraint_pattern = re.compile(
            r'O\(\s*[n1]\s*\)|in[\s-]place|without\s+(?:extra|additional)\s+space|'
            r'constant\s+space|linear\s+time|in[\s-]situ',
            re.IGNORECASE
        )
        self._complexity_notation = re.compile(
            r'O\([^)]+\)', re.IGNORECASE
        )

    def extract(self, query: str) -> QueryFeatures:
        query_lower = query.lower()
        words = query_lower.split()
        word_set = set(words)

        structural = self._extract_structural(query, words)
        lexical = self._extract_lexical(words, word_set)
        intent = self._extract_intent(query_lower, word_set)
        complexity_signals = self._extract_complexity(query_lower, word_set)

        all_capabilities = set()
        if lexical["code_keyword_count"] >= 2:
            all_capabilities.add("coding")
        if lexical["algorithm_term_count"] >= 1:
            all_capabilities.add("coding")
            all_capabilities.add("reasoning")
        if intent["is_explanation"]:
            all_capabilities.add("technical")
        if intent["is_creative"]:
            all_capabilities.add("creative")
        if intent["is_debugging"]:
            all_capabilities.add("coding")
            all_capabilities.add("reasoning")
        if intent["is_comparison"]:
            all_capabilities.add("reasoning")
            all_capabilities.add("technical")
        if complexity_signals["requires_optimization"]:
            all_capabilities.add("reasoning")

        if not all_capabilities:
            all_capabilities.add("general")

        query_type = self._classify_query_type(intent, lexical, complexity_signals)

        feature_vector = self._build_feature_vector(
            structural, lexical, intent, complexity_signals
        )

        return QueryFeatures(
            length=structural["length"],
            has_code_block=structural["has_code_block"],
            has_question=structural["has_question"],
            technical_term_ratio=lexical["technical_term_ratio"],
            code_keyword_count=lexical["code_keyword_count"],
            algorithm_term_count=lexical["algorithm_term_count"],
            complexity_term_count=complexity_signals["complexity_term_count"],
            is_implementation=intent["is_implementation"],
            is_explanation=intent["is_explanation"],
            is_debugging=intent["is_debugging"],
            is_comparison=intent["is_comparison"],
            is_creative=intent["is_creative"],
            has_constraints=complexity_signals["has_constraints"],
            requires_optimization=complexity_signals["requires_optimization"],
            multi_step=complexity_signals["multi_step"],
            query_type=query_type,
            feature_vector=feature_vector,
        )

    def _extract_structural(self, query: str, words: List[str]) -> Dict:
        has_code_block = "```" in query
        has_question = "?" in query
        has_code_syntax = bool(self._code_pattern.search(query))

        return {
            "length": len(words),
            "has_code_block": has_code_block,
            "has_question": has_question,
            "has_code_syntax": has_code_syntax,
        }

    def _extract_lexical(self, words: List[str], word_set: Set[str]) -> Dict:
        code_hits = len(word_set & CODE_KEYWORDS)
        algo_hits = len(word_set & ALGORITHM_KEYWORDS)
        tech_hits = len(word_set & TECHNICAL_TERMS)

        total_words = max(len(words), 1)
        technical_term_ratio = tech_hits / total_words

        bigrams = set()
        for i in range(len(words) - 1):
            bigrams.add(f"{words[i]} {words[i+1]}")

        algo_bigram_boost = 0
        algo_bigrams = {
            "dynamic programming", "binary search", "search tree",
            "linked list", "hash map", "priority queue", "depth first",
            "breadth first", "shortest path", "spanning tree",
            "two pointer", "sliding window", "divide and",
            "back tracking", "topological sort",
        }
        algo_bigram_boost = len(bigrams & algo_bigrams)

        return {
            "code_keyword_count": code_hits,
            "algorithm_term_count": algo_hits + algo_bigram_boost,
            "technical_term_ratio": technical_term_ratio,
        }

    def _extract_intent(self, query_lower: str, word_set: Set[str]) -> Dict:
        impl_signals = {"implement", "create", "build", "code", "develop", "program"}
        explain_signals = {"explain", "what", "how", "why", "describe", "define", "describe"}
        debug_signals = {"fix", "debug", "error", "bug", "broken", "not working", "fails", "crash"}
        compare_signals = {"compare", "vs", "versus", "difference", "differences", "better", "worse"}
        creative_signals = {"story", "poem", "creative", "brainstorm", "compose", "narrative", "fiction", "essay", "blog"}

        is_creative = bool(word_set & creative_signals) or bool(re.search(
            r'\b(?:write|create|compose)\b\s+(?:a|an|the)\s+(?:story|poem|essay|blog|article|narrative|song)',
            query_lower
        ))

        is_impl = (bool(word_set & impl_signals) or bool(re.search(
            r'\b(?:write|implement|create|build|code)\b\s+(?:a|an|the)\s+(?:function|class|method|program|algorithm|solution|implementation)',
            query_lower
        ))) and not is_creative

        is_explain = bool(word_set & explain_signals) or query_lower.startswith(("what", "how", "why"))
        is_debug = bool(word_set & debug_signals)
        is_compare = bool(word_set & compare_signals) and not is_explain

        return {
            "is_implementation": is_impl,
            "is_explanation": is_explain,
            "is_debugging": is_debug,
            "is_comparison": is_compare,
            "is_creative": is_creative,
        }

    def _extract_complexity(self, query_lower: str, word_set: Set[str]) -> Dict:
        complexity_hits = len(word_set & COMPLEXITY_KEYWORDS)
        has_constraints = bool(self._constraint_pattern.search(query_lower))
        has_complexity_notation = bool(self._complexity_notation.search(query_lower))

        optimization_signals = {"optimize", "efficient", "fastest", "minimum", "optimal"}
        requires_optimization = bool(word_set & optimization_signals) or has_complexity_notation

        multi_step_signals = {
            "first", "then", "next", "finally", "step", "steps",
            "process", "workflow", "pipeline", "chain",
        }
        multi_step = len(word_set & multi_step_signals) >= 2

        return {
            "complexity_term_count": complexity_hits,
            "has_constraints": has_constraints or has_complexity_notation,
            "requires_optimization": requires_optimization,
            "multi_step": multi_step,
        }

    def _classify_query_type(
        self, intent: Dict, lexical: Dict, complexity: Dict
    ) -> QueryType:
        if intent["is_implementation"] or lexical["code_keyword_count"] >= 2:
            return QueryType.IMPLEMENTATION
        if intent["is_debugging"]:
            return QueryType.DEBUGGING
        if intent["is_creative"]:
            return QueryType.CREATIVE
        if intent["is_comparison"]:
            return QueryType.COMPARISON
        if intent["is_explanation"]:
            return QueryType.EXPLANATION
        return QueryType.GENERAL

    def _build_feature_vector(
        self, structural: Dict, lexical: Dict, intent: Dict, complexity: Dict
    ) -> List[float]:
        return [
            float(structural["length"]),
            float(structural["has_code_block"]),
            float(structural["has_question"]),
            float(structural.get("has_code_syntax", False)),
            float(lexical["code_keyword_count"]),
            float(lexical["algorithm_term_count"]),
            float(lexical["technical_term_ratio"]),
            float(complexity["complexity_term_count"]),
            float(complexity["has_constraints"]),
            float(complexity["requires_optimization"]),
            float(complexity["multi_step"]),
            float(intent["is_implementation"]),
            float(intent["is_explanation"]),
            float(intent["is_debugging"]),
            float(intent["is_comparison"]),
            float(intent["is_creative"]),
        ]

    def compute_similarity(self, a: QueryFeatures, b: QueryFeatures) -> float:
        vec_a = a.feature_vector
        vec_b = b.feature_vector

        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        cosine = dot / (norm_a * norm_b)

        bonus = 0.0
        if a.query_type == b.query_type:
            bonus += 0.15
        if a.has_code_block == b.has_code_block:
            bonus += 0.05
        if abs(a.code_keyword_count - b.code_keyword_count) <= 1:
            bonus += 0.1
        if a.has_constraints == b.has_constraints:
            bonus += 0.1

        return min(1.0, cosine + bonus)
