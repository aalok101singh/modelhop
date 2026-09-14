from .config import Config
from .core.models import (
    Tier, ComplexityLevel, EmotionalTone, ModelConfig,
    QueryAnalysis, RoutingDecision, ProviderResponse,
    ConfidenceResult, CostAnalysis, TraceEntry, HopScoreResult,
    ShieldStatus, HubConfig, QueryFeatures, QueryType,
    Experience, PerformanceMetrics, ModelProfile, SubQuery
)
from .core.analyzer import QueryAnalyzer
from .core.router import Router
from .core.confidence import ConfidenceEngine
from .core.fallback import CascadeFallback
from .core.features import FeatureExtractor
from .core.memory import ExperienceMemory
from .core.performance import PerformanceTracker
from .core.learning_router import LearningRouter
from .core.adaptive_threshold import AdaptiveThreshold
from .core.reasoning import ReasoningEngine
from .core.decomposer import QueryDecomposer
from .registry.model_registry import ModelRegistry
from .tracking.cost_tracker import CostTracker
from .tracking.trace_logger import TraceLogger
from .tracking.hop_score import HopScore
from .shield.shield import Shield
from .hub.hub import Hub


class ModelHop:
    def __init__(self, config_path: str = None):
        self.config = Config(config_path)
        self.registry = ModelRegistry(self.config)
        self.models = self.registry.get_models()

        available_providers = []
        for model in self.models:
            p = self.registry.get_provider(model.name)
            if p is not None:
                available_providers.append(p)

        self.analyzer = QueryAnalyzer(available_providers)
        self.router = Router(self.models)

        self.feature_extractor = FeatureExtractor()
        self.memory = ExperienceMemory()
        self.performance = PerformanceTracker(self.memory)
        self.learning_router = LearningRouter(self.models, self.memory, self.performance)
        self.adaptive_threshold = AdaptiveThreshold(
            initial=self.config.get_routing_config().get("confidence_threshold", 0.7)
        )
        self.reasoning_engine = ReasoningEngine(self.memory, self.performance)
        self.decomposer = QueryDecomposer()

        self.confidence_engine = ConfidenceEngine(
            threshold=self.adaptive_threshold.get_threshold(),
            enable_consensus=self.config.get_routing_config().get("cross_model_consensus", True)
        )
        self.fallback = CascadeFallback(
            self.models,
            max_retries=self.config.get_routing_config().get("max_retries", 3)
        )
        self.cost_tracker = CostTracker()
        self.trace_logger = TraceLogger()
        self.hop_score = HopScore()
        self.shield = Shield(
            quality_threshold=self.config.get_shield_config().get("quality_threshold", 0.8)
        )
        self.hub = Hub()

        self.performance.rebuild_from_memory()

    async def route(self, query: str) -> ProviderResponse:
        query_features = self.feature_extractor.extract(query)
        analysis = await self.analyzer.analyze(query)

        decision, reasoning = self.learning_router.route(analysis, query_features)

        self.confidence_engine.threshold = self.adaptive_threshold.get_threshold()

        provider = self.registry.get_provider(decision.model.name)
        if provider is None:
            raise RuntimeError(f"No provider available for {decision.model.name}")

        response = await provider.generate(query)
        confidence = await self.confidence_engine.check(query, response, provider)

        fallback_count = 0
        while not confidence.is_confident and fallback_count < 3:
            fallback_decision = await self.fallback.handle_low_confidence(
                query, analysis, decision.model, confidence
            )
            if fallback_decision is None:
                break
            decision = fallback_decision
            provider = self.registry.get_provider(decision.model.name)
            if provider is None:
                break
            response = await provider.generate(query)
            confidence = await self.confidence_engine.check(query, response, provider)
            fallback_count += 1

        self.memory.record(
            query=query,
            query_features=query_features,
            analysis=analysis,
            decision=decision,
            response_quality=confidence.score,
            fallback_used=fallback_count > 0,
            latency_ms=response.latency_ms,
        )
        self.performance.record_outcome(
            model_name=decision.model.name,
            query_type=query_features.query_type,
            quality=confidence.score,
            latency_ms=response.latency_ms,
            fallback_used=fallback_count > 0,
        )
        self.adaptive_threshold.adjust(confidence.score)

        cost = self.cost_tracker.calculate(response, decision.model)
        trace = self.trace_logger.log(
            query=query,
            analysis=analysis,
            decision=decision,
            response=response,
            confidence=confidence,
            cost=cost,
            fallback_count=fallback_count
        )
        self.shield.check_quality(trace)
        self.hop_score.update(confidence.is_confident)

        return response


__all__ = [
    "ModelHop",
    "Config",
    "Tier", "ComplexityLevel", "EmotionalTone", "ModelConfig",
    "QueryAnalysis", "RoutingDecision", "ProviderResponse",
    "ConfidenceResult", "CostAnalysis", "TraceEntry",
    "HopScoreResult", "ShieldStatus", "HubConfig",
    "QueryFeatures", "QueryType", "Experience", "PerformanceMetrics",
    "ModelProfile", "SubQuery",
    "QueryAnalyzer", "Router", "ConfidenceEngine", "CascadeFallback",
    "FeatureExtractor", "ExperienceMemory", "PerformanceTracker",
    "LearningRouter", "AdaptiveThreshold", "ReasoningEngine", "QueryDecomposer",
    "ModelRegistry", "CostTracker", "TraceLogger", "HopScore",
    "Shield", "Hub"
]
