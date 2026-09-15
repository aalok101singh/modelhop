import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from .features import FeatureExtractor
from .models import (
    Experience,
    QueryAnalysis,
    QueryFeatures,
    QueryType,
    RoutingDecision,
)
from .persistence import atomic_write_json

MEMORY_FILE = "modelhop_memory.json"
TRACE_FILE = "trace_log.json"


class ExperienceMemory:
    """Stores routing experiences and provides similarity search for learning."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.getcwd()
        self.experiences: List[Experience] = []
        self.feature_extractor = FeatureExtractor()
        self._by_query_type: Dict[QueryType, List[Experience]] = defaultdict(list)
        self._by_model: Dict[str, List[Experience]] = defaultdict(list)
        self._load_from_trace_log()
        self._load_persistent_memory()

    def _get_memory_path(self) -> str:
        return os.path.join(self.data_dir, MEMORY_FILE)

    def _get_trace_path(self) -> str:
        return os.path.join(self.data_dir, TRACE_FILE)

    def _load_persistent_memory(self):
        path = self._get_memory_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("experiences", []):
                try:
                    exp = Experience(
                        query_id=item.get("query_id", ""),
                        query=item.get("query", ""),
                        query_features=(
                            QueryFeatures(**item["query_features"])
                            if item.get("query_features")
                            else None
                        ),
                        response_quality=item.get("response_quality", 0.0),
                        fallback_used=item.get("fallback_used", False),
                        model_name=item.get("model_name", ""),
                        tier=item.get("tier", ""),
                        query_type=QueryType(item.get("query_type", "general")),
                        latency_ms=item.get("latency_ms", 0),
                        timestamp=(
                            datetime.fromisoformat(item["timestamp"])
                            if item.get("timestamp")
                            else datetime.now()
                        ),
                    )
                    self._index_experience(exp)
                except Exception:
                    continue
        except Exception:
            pass

    def _load_from_trace_log(self):
        path = self._get_trace_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                traces = json.load(f)
            for trace in traces:
                try:
                    query = trace.get("query", "")
                    features = self.feature_extractor.extract(query) if query else None

                    exp = Experience(
                        query_id=trace.get("query_id", ""),
                        query=query,
                        query_features=features,
                        response_quality=trace.get("confidence", 0.85),
                        fallback_used=trace.get("fallback_used", False),
                        model_name=trace.get("model", ""),
                        tier=trace.get("tier", ""),
                        query_type=(
                            self._infer_query_type(features) if features else QueryType.GENERAL
                        ),
                        latency_ms=trace.get("latency_ms", 0),
                        timestamp=(
                            datetime.fromisoformat(trace["timestamp"])
                            if trace.get("timestamp")
                            else datetime.now()
                        ),
                    )
                    self._index_experience(exp)
                except Exception:
                    continue
        except Exception:
            pass

    def _infer_query_type(self, features: QueryFeatures) -> QueryType:
        return features.query_type

    def _index_experience(self, exp: Experience):
        self.experiences.append(exp)
        self._by_query_type[exp.query_type].append(exp)
        if exp.model_name:
            self._by_model[exp.model_name].append(exp)

    def record(
        self,
        query: str,
        query_features: QueryFeatures,
        analysis: QueryAnalysis,
        decision: RoutingDecision,
        response_quality: float,
        fallback_used: bool,
        latency_ms: int,
    ):
        exp = Experience(
            query_id=datetime.now().strftime("%Y%m%d%H%M%S%f"),
            query=query,
            query_features=query_features,
            analysis=analysis,
            decision=decision,
            response_quality=response_quality,
            fallback_used=fallback_used,
            model_name=decision.model.name,
            tier=decision.tier.value,
            query_type=query_features.query_type,
            latency_ms=latency_ms,
            timestamp=datetime.now(),
        )
        self._index_experience(exp)
        self._persist()

    def find_similar(
        self, query_features: QueryFeatures, top_k: int = 5, min_similarity: float = 0.4
    ) -> List[Experience]:
        if not self.experiences:
            return []

        scored = []
        for exp in self.experiences:
            if exp.query_features is None:
                continue
            sim = self.feature_extractor.compute_similarity(query_features, exp.query_features)
            if sim >= min_similarity:
                scored.append((exp, sim))

        scored.sort(key=lambda x: -x[1])
        return [exp for exp, _ in scored[:top_k]]

    def find_similar_by_type(self, query_type: QueryType, limit: int = 20) -> List[Experience]:
        return self._by_query_type.get(query_type, [])[:limit]

    def get_model_history(self, model_name: str) -> List[Experience]:
        return self._by_model.get(model_name, [])

    def get_model_quality_for_type(self, model_name: str, query_type: QueryType) -> Optional[float]:
        exps = [e for e in self._by_model.get(model_name, []) if e.query_type == query_type]
        if not exps:
            return None
        return sum(e.response_quality for e in exps) / len(exps)

    def get_overall_stats(self) -> Dict:
        if not self.experiences:
            return {"total": 0, "avg_quality": 0.0, "fallback_rate": 0.0}

        total = len(self.experiences)
        avg_quality = sum(e.response_quality for e in self.experiences) / total
        fallback_count = sum(1 for e in self.experiences if e.fallback_used)

        model_usage = defaultdict(int)
        for exp in self.experiences:
            model_usage[exp.model_name] += 1

        return {
            "total": total,
            "avg_quality": avg_quality,
            "fallback_rate": fallback_count / total,
            "model_usage": dict(model_usage),
            "type_distribution": {qt.value: len(exps) for qt, exps in self._by_query_type.items()},
        }

    def _persist(self):
        path = self._get_memory_path()
        data = {"version": "1.0", "experiences": []}
        for exp in self.experiences[-500:]:
            item = {
                "query_id": exp.query_id,
                "query": exp.query,
                "response_quality": exp.response_quality,
                "fallback_used": exp.fallback_used,
                "model_name": exp.model_name,
                "tier": exp.tier,
                "query_type": exp.query_type.value,
                "latency_ms": exp.latency_ms,
                "timestamp": exp.timestamp.isoformat(),
            }
            if exp.query_features:
                item["query_features"] = {
                    "length": exp.query_features.length,
                    "has_code_block": exp.query_features.has_code_block,
                    "has_question": exp.query_features.has_question,
                    "technical_term_ratio": exp.query_features.technical_term_ratio,
                    "code_keyword_count": exp.query_features.code_keyword_count,
                    "algorithm_term_count": exp.query_features.algorithm_term_count,
                    "complexity_term_count": exp.query_features.complexity_term_count,
                    "is_implementation": exp.query_features.is_implementation,
                    "is_explanation": exp.query_features.is_explanation,
                    "is_debugging": exp.query_features.is_debugging,
                    "is_comparison": exp.query_features.is_comparison,
                    "is_creative": exp.query_features.is_creative,
                    "has_constraints": exp.query_features.has_constraints,
                    "requires_optimization": exp.query_features.requires_optimization,
                    "multi_step": exp.query_features.multi_step,
                    "query_type": exp.query_features.query_type.value,
                    "feature_vector": exp.query_features.feature_vector,
                }
            data["experiences"].append(item)

        try:
            atomic_write_json(path, data)
        except Exception:
            pass
