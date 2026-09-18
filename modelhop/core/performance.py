import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .memory import ExperienceMemory
from .models import ModelProfile, PerformanceMetrics, QueryType

PERF_FILE = "modelhop_performance.json"


class PerformanceTracker:
    """Tracks per-model, per-query-type performance with decay weighting."""

    def __init__(self, memory: ExperienceMemory, data_dir: str = None, models=None):
        self.memory = memory
        self.data_dir = data_dir or os.getcwd()
        self.profiles: Dict[str, ModelProfile] = {}
        self._decay_half_life_days = 30
        self._models_by_name: Dict[str, object] = {}
        if models:
            self.set_models(models)
        self._load()

    def _get_path(self) -> str:
        return os.path.join(self.data_dir, PERF_FILE)

    def _store(self):
        from .persistence import SignedStore

        return SignedStore(schema_version=1)

    def _load(self):
        from .persistence import StateIntegrityError

        path = self._get_path()
        if not os.path.exists(path):
            return
        try:
            try:
                data = self._store().load(path)
            except StateIntegrityError:
                import warnings

                warnings.warn(f"Performance store {path} failed integrity check; resetting.")
                return
            if not isinstance(data, dict):
                return
            for name, profile_data in data.get("profiles", {}).items():
                try:
                    profile = ModelProfile(**profile_data)
                except Exception:
                    continue
                self.profiles[name] = profile
        except Exception:
            pass

    def _persist(self):
        from .persistence import atomic_write_json as _atomic

        path = self._get_path()
        data = {"version": "1.0", "profiles": {}}
        for name, profile in self.profiles.items():
            data["profiles"][name] = profile.model_dump()
        try:
            self._store().save(path, data)
        except Exception:
            try:
                _atomic(path, data)
            except Exception:
                pass

    def rebuild_from_memory(self):
        self.profiles.clear()
        for exp in self.memory.experiences:
            if not exp.model_name:
                continue
            self._update_from_experience(exp)
        self._persist()

    def set_models(self, models) -> None:
        self._models_by_name = {m.name: m for m in (models or [])}
        for name, cfg in self._models_by_name.items():
            if name in self.profiles:
                try:
                    self.profiles[name].provider = cfg.provider
                    self.profiles[name].tier = cfg.tier
                    self.profiles[name].static_capabilities = list(cfg.capabilities)
                except Exception:
                    pass

    def _ensure_profile(self, model_name: str) -> "ModelProfile":
        if model_name not in self.profiles:
            cfg = self._models_by_name.get(model_name)
            if cfg is not None:
                try:
                    self.profiles[model_name] = ModelProfile(
                        name=model_name,
                        provider=cfg.provider,
                        tier=cfg.tier,
                        static_capabilities=list(cfg.capabilities),
                    )
                except Exception:
                    self.profiles[model_name] = ModelProfile(name=model_name)
            else:
                self.profiles[model_name] = ModelProfile(name=model_name)
        return self.profiles[model_name]

    def _update_from_experience(self, exp):
        from .models import PerformanceMetrics as _PM

        model_name = exp.model_name
        profile = self._ensure_profile(model_name)
        qt_key = exp.query_type.value

        if qt_key not in profile.performance_by_query_type:
            profile.performance_by_query_type[qt_key] = _PM().model_dump()

        metrics_data = profile.performance_by_query_type[qt_key]
        metrics = _PM(**metrics_data)

        age_days = (datetime.now() - exp.timestamp).days if exp.timestamp else 0
        w = 0.5 ** (age_days / self._decay_half_life_days)

        W = float(getattr(metrics, "weight_sum", 0.0) or 0.0)
        old_quality = metrics.avg_quality
        old_latency = metrics.avg_latency_ms

        denom = W + w
        if denom > 0:
            metrics.avg_quality = (old_quality * W + exp.response_quality * w) / denom
            metrics.avg_latency_ms = int((old_latency * W + exp.latency_ms * w) / denom)
            metrics.fallback_rate = (
                metrics.fallback_rate * W + (w if exp.fallback_used else 0.0)
            ) / denom
        metrics.weight_sum = W + w
        metrics.sample_count += 1
        metrics.success_rate = 1.0 - metrics.fallback_rate

        if metrics.sample_count > 1:
            metrics.quality_stddev = abs(metrics.avg_quality - old_quality) * 0.3
        else:
            metrics.quality_stddev = 0.0

        profile.performance_by_query_type[qt_key] = metrics.model_dump()

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
        profile = self._ensure_profile(model_name)
        qt_key = query_type.value

        if qt_key not in profile.performance_by_query_type:
            profile.performance_by_query_type[qt_key] = PerformanceMetrics().model_dump()

        metrics_data = profile.performance_by_query_type[qt_key]
        metrics = PerformanceMetrics(**metrics_data)

        # Fresh outcomes have weight 1.0; decay applies on age via rebuild path.
        W = float(getattr(metrics, "weight_sum", 0.0) or 0.0)
        w = 1.0
        denom = W + w
        metrics.avg_quality = (metrics.avg_quality * W + quality * w) / denom if denom else quality
        metrics.avg_latency_ms = (
            int((metrics.avg_latency_ms * W + latency_ms * w) / denom) if denom else latency_ms
        )
        metrics.fallback_rate = (
            (metrics.fallback_rate * W + (w if fallback_used else 0.0)) / denom if denom else 0.0
        )
        metrics.weight_sum = denom
        metrics.sample_count += 1
        metrics.success_rate = 1.0 - metrics.fallback_rate

        profile.performance_by_query_type[qt_key] = metrics.model_dump()

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
