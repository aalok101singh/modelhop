from typing import Optional

from .config import Config
from .core.adaptive_threshold import AdaptiveThreshold
from .core.analyzer import QueryAnalyzer
from .core.confidence import ConfidenceEngine
from .core.decomposer import QueryDecomposer
from .core.fallback import CascadeFallback
from .core.features import FeatureExtractor
from .core.learning_router import LearningRouter
from .core.memory import ExperienceMemory
from .core.models import (
    ComplexityLevel,
    ConfidenceResult,
    CostAnalysis,
    EmotionalTone,
    Experience,
    HopScoreResult,
    HubConfig,
    ModelConfig,
    ModelProfile,
    PerformanceMetrics,
    ProviderResponse,
    QueryAnalysis,
    QueryFeatures,
    QueryType,
    RoutingDecision,
    ShieldStatus,
    SubQuery,
    Tier,
    TraceEntry,
)
from .core.performance import PerformanceTracker
from .core.reasoning import ReasoningEngine
from .core.router import Router
from .hub.hub import Hub
from .registry.model_registry import ModelRegistry
from .shield.shield import Shield
from .tracking.cost_tracker import CostTracker, estimate_cost
from .tracking.hop_score import HopScore
from .tracking.trace_logger import TraceLogger


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
            enable_consensus=self.config.get_routing_config().get("cross_model_consensus", True),
        )
        self.fallback = CascadeFallback(
            self.models, max_retries=self.config.get_routing_config().get("max_retries", 3)
        )
        self.cost_tracker = CostTracker()
        self.trace_logger = TraceLogger()
        self.hop_score = HopScore()
        self.shield = Shield(
            quality_threshold=self.config.get_shield_config().get("quality_threshold", 0.8)
        )
        self.hub = Hub()

        self.decompose_queries = self.config.get_routing_config().get("decompose_queries", True)

        self.performance.rebuild_from_memory()

    async def route(self, query: str) -> ProviderResponse:
        query_features = self.feature_extractor.extract(query)
        analysis = await self.analyzer.analyze(query)

        decision, reasoning = self.learning_router.route(analysis, query_features)

        self.confidence_engine.threshold = self.adaptive_threshold.get_threshold()

        if self.decompose_queries:
            sub_queries = self.decomposer.decompose(query, analysis)
            if len(sub_queries) > 1:
                return await self._route_decomposed(
                    query, query_features, analysis, decision, sub_queries
                )

        response, confidence, decision, fallback_total = await self._generate_and_check(
            query, analysis, query_features, decision
        )

        self._finish_route(
            query, query_features, analysis, decision, response, confidence, fallback_total
        )
        return response

    async def _generate_and_check(
        self,
        query: str,
        analysis: QueryAnalysis,
        query_features: QueryFeatures,
        decision: RoutingDecision,
    ):
        max_retries = self.fallback.max_retries
        tried = {decision.model.name}
        current = decision
        fallback_count = 0
        response = None
        provider = None

        while fallback_count < max_retries + 1:
            provider = self.registry.get_provider(current.model.name)
            if provider is None:
                nxt = self._next_fallback_decision(current, tried)
                if nxt is None:
                    break
                current = nxt
                tried.add(nxt.model.name)
                fallback_count += 1
                continue
            try:
                response = await provider.generate(query)
                break
            except Exception:
                nxt = self._next_fallback_decision(current, tried)
                if nxt is None:
                    break
                current = nxt
                tried.add(nxt.model.name)
                fallback_count += 1
                continue

        if response is None:
            raise RuntimeError(f"No provider could handle the query after {max_retries} retries")

        confidence = await self.confidence_engine.check(
            query,
            response,
            provider,
            consensus_provider=self._get_consensus_provider(current.model.name),
            query_features=query_features,
        )

        conf_fallback_count = 0
        while not confidence.is_confident and conf_fallback_count < max_retries:
            fb = await self.fallback.handle_low_confidence(
                query, analysis, current.model, confidence
            )
            if fb is None:
                fb = self._next_fallback_decision(current, tried)
                if fb is None:
                    break
            current = fb
            tried.add(current.model.name)
            fb_provider = self.registry.get_provider(current.model.name)
            if fb_provider is None:
                fb = self._next_fallback_decision(current, tried)
                if fb is None:
                    break
                current = fb
                tried.add(current.model.name)
                fb_provider = self.registry.get_provider(current.model.name)
                if fb_provider is None:
                    break
            provider = fb_provider
            try:
                response = await provider.generate(query)
            except Exception:
                fb = self._next_fallback_decision(current, tried)
                if fb is None:
                    break
                current = fb
                tried.add(current.model.name)
                continue
            confidence = await self.confidence_engine.check(
                query,
                response,
                provider,
                consensus_provider=self._get_consensus_provider(current.model.name),
                query_features=query_features,
            )
            conf_fallback_count += 1

        return response, confidence, current, fallback_count + conf_fallback_count

    async def _route_decomposed(
        self,
        query: str,
        query_features: QueryFeatures,
        analysis: QueryAnalysis,
        parent_decision: RoutingDecision,
        sub_queries,
    ) -> ProviderResponse:
        responses = []
        confidences = []
        costs = []
        fallback_used = False
        total_fallback = 0
        total_latency = 0
        tokens_in = 0
        tokens_out = 0
        perf_records = []
        tracking = self.config.get_tracking_config()
        log_queries = tracking.get("log_queries", True)
        log_costs = tracking.get("log_costs", True)

        for sub in sub_queries:
            try:
                sub_features = self.feature_extractor.extract(sub.query)
                sub_decision, _ = self.learning_router.route(sub.analysis, sub_features)
                self.confidence_engine.threshold = self.adaptive_threshold.get_threshold()
                resp, conf, final_decision, fb = await self._generate_and_check(
                    sub.query, sub.analysis, sub_features, sub_decision
                )

                responses.append(resp)
                confidences.append(conf.score)
                fallback_used = fallback_used or (fb > 0)
                total_fallback += fb
                total_latency += resp.latency_ms
                tokens_in += resp.tokens_in
                tokens_out += resp.tokens_out
                perf_records.append(
                    (
                        final_decision.model.name,
                        sub_features.query_type,
                        conf.score,
                        resp.latency_ms,
                        fb > 0,
                    )
                )
                if log_costs:
                    costs.append(self.cost_tracker.calculate(resp, final_decision.model))
                else:
                    costs.append(estimate_cost(resp, final_decision.model))
            except Exception:
                continue

        if not responses:
            raise RuntimeError(f"All sub-queries for '{query}' failed")

        composite = ProviderResponse(
            content=self.decomposer.synthesize(responses),
            model_used="decomposed",
            provider="decomposed",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=total_latency,
        )

        min_confidence = min(confidences)
        composite_confidence = ConfidenceResult(
            score=min_confidence,
            is_confident=min_confidence >= self.confidence_engine.threshold,
            threshold=self.confidence_engine.threshold,
            reasoning=f"Minimum confidence across {len(confidences)} sub-queries",
        )

        if log_queries:
            for model_name, qtype, quality, latency, used_fb in perf_records:
                self.performance.record_outcome(
                    model_name=model_name,
                    query_type=qtype,
                    quality=quality,
                    latency_ms=latency,
                    fallback_used=used_fb,
                )
            self.memory.record(
                query=query,
                query_features=query_features,
                analysis=analysis,
                decision=parent_decision,
                response_quality=composite_confidence.score,
                fallback_used=fallback_used,
                latency_ms=total_latency,
            )
            self.adaptive_threshold.adjust(composite_confidence.score)

        if costs:
            actual = sum(c.actual_cost for c in costs)
            would = sum(c.would_have_cost for c in costs)
            cost = CostAnalysis(
                actual_cost=actual,
                would_have_cost=would,
                savings=would - actual,
                savings_percentage=(would - actual) / would * 100 if would > 0 else 0,
                model_used="decomposed",
                tier=parent_decision.tier.value,
            )
        else:
            cost = estimate_cost(composite, parent_decision.model)

        if log_queries:
            trace = self.trace_logger.log(
                query=query,
                analysis=analysis,
                decision=parent_decision,
                response=composite,
                confidence=composite_confidence,
                cost=cost,
                fallback_count=total_fallback,
            )
            self.shield.check_quality(trace)
            self.hop_score.update(composite_confidence.is_confident)

        return composite

    def _finish_route(
        self,
        query: str,
        query_features: QueryFeatures,
        analysis: QueryAnalysis,
        decision: RoutingDecision,
        response: ProviderResponse,
        confidence: ConfidenceResult,
        fallback_count: int,
    ) -> None:
        tracking = self.config.get_tracking_config()
        log_queries = tracking.get("log_queries", True)
        log_costs = tracking.get("log_costs", True)

        if log_queries:
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

        if log_costs:
            cost = self.cost_tracker.calculate(response, decision.model)
        else:
            cost = estimate_cost(response, decision.model)

        if log_queries:
            trace = self.trace_logger.log(
                query=query,
                analysis=analysis,
                decision=decision,
                response=response,
                confidence=confidence,
                cost=cost,
                fallback_count=fallback_count,
            )
            self.shield.check_quality(trace)
            self.hop_score.update(confidence.is_confident)

    def _get_consensus_provider(self, exclude_model: str):
        for name, provider in self.registry.get_available_providers().items():
            if name != exclude_model:
                return provider
        return None

    def _next_fallback_decision(
        self, current_decision: RoutingDecision, tried_models
    ) -> Optional[RoutingDecision]:
        for name in self.registry.get_available_providers():
            if name in tried_models or name == current_decision.model.name:
                continue
            model = self.registry.get_model(name)
            if model:
                return RoutingDecision(
                    model=model,
                    tier=model.tier,
                    reason=f"Fallback from {current_decision.model.name}",
                    alternatives=[],
                )
        return None


__all__ = [
    "ModelHop",
    "Config",
    "Tier",
    "ComplexityLevel",
    "EmotionalTone",
    "ModelConfig",
    "QueryAnalysis",
    "RoutingDecision",
    "ProviderResponse",
    "ConfidenceResult",
    "CostAnalysis",
    "TraceEntry",
    "HopScoreResult",
    "ShieldStatus",
    "HubConfig",
    "QueryFeatures",
    "QueryType",
    "Experience",
    "PerformanceMetrics",
    "ModelProfile",
    "SubQuery",
    "QueryAnalyzer",
    "Router",
    "ConfidenceEngine",
    "CascadeFallback",
    "FeatureExtractor",
    "ExperienceMemory",
    "PerformanceTracker",
    "LearningRouter",
    "AdaptiveThreshold",
    "ReasoningEngine",
    "QueryDecomposer",
    "ModelRegistry",
    "CostTracker",
    "TraceLogger",
    "HopScore",
    "Shield",
    "Hub",
]
