import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .memory import ExperienceMemory
from .models import ModelProfile, PerformanceMetrics, QueryType

PERF_FILE = "modelhop_performance.json"


class PerformanceTracker:
    """Tracks per-model, per-query-type performance with decay weighting."""

    def __init__(self, memory: ExperienceMemory, data_dir: str = None):
        self.memory = memory
        self.data_dir = data_dir or os.getcwd()
        self.profiles: Dict[str, ModelProfile] = {}
        self._decay_half_life_days = 30
        self._load()

    def _get_path(self) -> str:
        return os.path.join(self.data_dir, PERF_FILE)

    def _load(self):
        path = self._get_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, profile_data in data.get("profiles", {}).items():
                profile = ModelProfile(**profile_data)
                self.profiles[name] = profile
        except Exception:
            pass

    def _persist(self):
        path = self._get_path()
        data = {
            "version": "1.0",
            "profiles": {}
        }
        for name, profile in self.profiles.items():
            data["profiles"][name] = profile.dict()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def rebuild_from_memory(self):
        self.profiles.clear()
        for exp in self.memory.experiences:
            if not exp.model_name:
                continue
            self._update_from_experience(exp)
        self._persist()

    def _update_from_experience(self, exp):
        model_name = exp.model_name
        if model_name not in self.profiles:
            self.profiles[model_name] = ModelProfile(
                name=model_name,
                query_type=exp.query_type,
            )

        profile = self.profiles[model_name]
        qt_key = exp.query_type.value

        if qt_key not in profile.performance_by_query_type:
            profile.performance_by_query_type[qt_key] = PerformanceMetrics().dict()

        metrics_data = profile.performance_by_query_type[qt_key]
        metrics = PerformanceMetrics(**metrics_data)

        age_days = (datetime.now() - exp.timestamp).days if exp.timestamp else 0
        weight = 0.5 ** (age_days / self._decay_half_life_days)

        n = metrics.sample_count
        old_quality = metrics.avg_quality
        old_latency = metrics.avg_latency_ms

        metrics.sample_count += 1
        metrics.avg_quality = (old_quality * n + exp.response_quality * weight) / (n + weight)
        metrics.avg_latency_ms = int((old_latency * n + exp.latency_ms * weight) / (n + weight))

        if metrics.sample_count > 1:
            metrics.quality_stddev = abs(metrics.avg_quality - old_quality) * 0.3
        else:
            metrics.quality_stddev = 0.0

        total_fallback = metrics.fallback_rate * n
        if exp.fallback_used:
            total_fallback += weight
        metrics.fallback_rate = total_fallback / (n + weight)
        metrics.success_rate = 1.0 - metrics.fallback_rate

        profile.performance_by_query_type[qt_key] = metrics.dict()

        all_qualities = []
        for qt, m_data in profile.performance_by_query_type.items():
            m = PerformanceMetrics(**m_data)
            if m.sample_count > 0:
                all_qualities.append(m.avg_quality)
        if all_qualities:
            profile.overall_quality = sum(all_qualities) / len(all_qualities)

        all_latencies = []
        for qt, m_data in profile.performance_by_query_type.items():
            m = PerformanceMetrics(**m_data)
            if m.sample_count > 0:
                all_latencies.append(m.avg_latency_ms)
        if all_latencies:
            profile.avg_latency_ms = int(sum(all_latencies) / len(all_latencies))

    def record_outcome(
        self,
        model_name: str,
        query_type: QueryType,
        quality: float,
        latency_ms: int,
        fallback_used: bool,
    ):
        if model_name not in self.profiles:
            self.profiles[model_name] = ModelProfile(name=model_name)

        profile = self.profiles[model_name]
        qt_key = query_type.value

        if qt_key not in profile.performance_by_query_type:
            profile.performance_by_query_type[qt_key] = PerformanceMetrics().dict()

        metrics_data = profile.performance_by_query_type[qt_key]
        metrics = PerformanceMetrics(**metrics_data)

        n = metrics.sample_count
        metrics.sample_count = n + 1
        metrics.avg_quality = (metrics.avg_quality * n + quality) / (n + 1)
        metrics.avg_latency_ms = int((metrics.avg_latency_ms * n + latency_ms) / (n + 1))
        total_fallback = metrics.fallback_rate * n + (1.0 if fallback_used else 0.0)
        metrics.fallback_rate = total_fallback / (n + 1)
        metrics.success_rate = 1.0 - metrics.fallback_rate

        profile.performance_by_query_type[qt_key] = metrics.dict()

        all_q = [
            PerformanceMetrics(**d).avg_quality
            for d in profile.performance_by_query_type.values()
            if PerformanceMetrics(**d).sample_count > 0
        ]
        if all_q:
            profile.overall_quality = sum(all_q) / len(all_q)

        self._persist()

    def get_metrics(self, model_name: str, query_type: QueryType) -> Optional[PerformanceMetrics]:
        profile = self.profiles.get(model_name)
        if not profile:
            return None
        qt_key = query_type.value
        if qt_key not in profile.performance_by_query_type:
            return None
        return PerformanceMetrics(**profile.performance_by_query_type[qt_key])

    def get_quality(self, model_name: str, query_type: QueryType = None) -> float:
        if query_type:
            metrics = self.get_metrics(model_name, query_type)
            if metrics and metrics.sample_count >= 2:
                return metrics.avg_quality

        profile = self.profiles.get(model_name)
        if profile:
            return profile.overall_quality
        return 0.5

    def get_recommendation(
        self, query_type: QueryType, min_samples: int = 2
    ) -> List[Tuple[str, float, int]]:
        recommendations = []
        for model_name, profile in self.profiles.items():
            qt_key = query_type.value
            if qt_key in profile.performance_by_query_type:
                metrics = PerformanceMetrics(**profile.performance_by_query_type[qt_key])
                if metrics.sample_count >= min_samples:
                    score = metrics.avg_quality * (1.0 - metrics.fallback_rate * 0.3)
                    recommendations.append((model_name, score, metrics.sample_count))

        recommendations.sort(key=lambda x: -x[1])
        return recommendations

    def get_fallback_prone_models(self, threshold: float = 0.3) -> List[str]:
        prone = []
        for model_name, profile in self.profiles.items():
            for qt_key, m_data in profile.performance_by_query_type.items():
                metrics = PerformanceMetrics(**m_data)
                if metrics.sample_count >= 3 and metrics.fallback_rate > threshold:
                    prone.append(model_name)
                    break
        return prone

    def get_all_profiles(self) -> Dict[str, ModelProfile]:
        return self.profiles.copy()
