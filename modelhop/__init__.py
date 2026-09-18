import hashlib
import json as json_mod
from typing import Dict, List, Optional

from .config import Config
from .core.adaptive_threshold import AdaptiveThreshold
from .core.analyzer import QueryAnalyzer
from .core.calibration import Calibrator
from .core.confidence import ConfidenceEngine
from .core.decomposer import QueryDecomposer
from .core.fallback import CascadeFallback
from .core.features import FeatureExtractor
from .core.health import HealthRegistry
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
    PerformanceCard,
    PerformanceMetrics,
    ProviderResponse,
    QueryAnalysis,
    QueryFeatures,
    QueryType,
    RouteResult,
    RoutingDecision,
    ShieldStatus,
    SubQuery,
    Tier,
    TraceEntry,
    TrustProfile,
    VerifierResult,
)
from .core.performance import PerformanceTracker
from .core.reasoning import ReasoningEngine
from .core.router import Router
from .core.secrets import EnvSecretsProvider
from .hub.hub import Hub
from .registry.model_registry import ModelRegistry
from .shield.shield import Shield
from .tracking.cost_tracker import CostTracker, PriceBook, estimate_cost
from .tracking.hop_score import HopScore, is_optimal_hop
from .tracking.ledger import DecisionLedger
from .tracking.trace_logger import TraceLogger


class _CacheTrustMiss(Exception):
    """Internal: a cache hit failed current trust requirements (=> miss)."""


def _tenant_of(context: dict) -> str:
    """Canonical tenant: documented `tenant_tier` wins, legacy `tenant` fallback."""
    context = context or {}
    return str(context.get("tenant_tier", context.get("tenant", "default")))


def _trust_digest(trust_required: dict) -> str:
    """Canonical short hash of per-call trust requirements for cache keys."""
    try:
        raw = json_mod.dumps(trust_required or {}, sort_keys=True, default=str)
    except Exception:
        raw = str(sorted((trust_required or {}).items()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ModelHop:
    """One brain, many bodies: SDK is the brain; CLI/HTTP are thin shells."""

    def __init__(self, config_path: str = None, secrets=None):
        self.config = Config(config_path)
        routing = self.config.get_routing_config()
        # Secrets: env-based default, chainable.
        if secrets is None:
            try:
                secrets = EnvSecretsProvider()
            except Exception:
                secrets = None
        self.secrets = secrets
        self.health = HealthRegistry()
        self.registry = ModelRegistry(self.config, secrets=secrets, health=self.health)
        # Share health registry.
        if getattr(self.registry, "health", None) is not None:
            try:
                self.health = self.registry.health or self.health
            except Exception:
                pass
        self.models = self.registry.get_models()

        self.trust_policy: Dict = dict(routing.get("trust_policy", {}) or {})
        self.fail_closed: bool = bool(routing.get("fail_closed", True))
        self.policy_version: str = str(routing.get("policy_version", "1"))
        self.cost_reference: str = str(routing.get("cost_savings_reference", "max"))
        self.llm_analysis: bool = bool(routing.get("llm_analysis", False))
        self.enable_consensus: bool = bool(routing.get("cross_model_consensus", False))
        self.decompose_queries: bool = bool(routing.get("decompose_queries", True))

        available_providers = []
        for model in self.models:
            p = self.registry.get_provider(model.name)
            if p is not None:
                available_providers.append(p)

        self.analyzer = QueryAnalyzer(available_providers, enable_llm=self.llm_analysis)
        self.router = Router(self.models, trust_policy=self.trust_policy)

        self.feature_extractor = FeatureExtractor()
        self.memory = ExperienceMemory()
        self.performance = PerformanceTracker(self.memory, models=self.models)
        self.learning_router = LearningRouter(
            self.models, self.memory, self.performance, trust_policy=self.trust_policy
        )
        self.adaptive_threshold = AdaptiveThreshold(
            initial=routing.get("confidence_threshold", 0.7)
        )
        self.reasoning_engine = ReasoningEngine(self.memory, self.performance)
        self.decomposer = QueryDecomposer()

        # Calibration + bandit (signed persistence).
        try:
            from .core.persistence import SignedStore as _SS

            _store = _SS(schema_version=1)
        except Exception:
            _store = None
        self._store = _store
        self.calibrator = Calibrator()
        if _store is not None:
            try:
                self.calibrator = Calibrator.load(_store)
            except Exception:
                pass
        self.confidence_engine = ConfidenceEngine(
            threshold=self.adaptive_threshold.get_threshold(),
            enable_consensus=self.enable_consensus,
            fail_closed=self.fail_closed,
            calibrator=self.calibrator,
        )
        self.fallback = CascadeFallback(self.models, max_retries=routing.get("max_retries", 3))
        # Price book + cost tracker.
        try:
            price_book = PriceBook.from_models(self.models, reference=self.cost_reference)
        except Exception:
            price_book = None
        self.cost_tracker = CostTracker(
            price_book=price_book,
            all_models=self.models,
            cost_savings_reference=self.cost_reference,
        )
        self.trace_logger = TraceLogger()
        self.hop_score = HopScore()
        self.shield = Shield(
            quality_threshold=self.config.get_shield_config().get("quality_threshold", 0.8)
        )
        self.hub = Hub()
        self.ledger = DecisionLedger()

        # Policy engine + bandit.
        try:
            from .core.policy.bandit import ContextualBandit
            from .core.policy.engine import default_engine

            self.policy_engine = default_engine(self.trust_policy, health=self.health)
            self.bandit = ContextualBandit()
            if _store is not None:
                try:
                    self.bandit = ContextualBandit.load(_store)
                except Exception:
                    pass
            # Seed priors from performance profiles.
            try:
                for _name, _prof in self.performance.get_all_profiles().items():
                    for _qt, _mdata in _prof.performance_by_query_type.items():
                        _m = PerformanceMetrics(**_mdata)
                        if _m.sample_count >= 2:
                            for _bucket in ("simple", "medium", "complex"):
                                _key = f"{_qt}x{_bucket}xdefault"
                                self.bandit.seed_prior(
                                    _name, _key, _m.avg_quality, min(_m.sample_count, 5)
                                )
            except Exception:
                pass
        except Exception:
            self.policy_engine = None
            self.bandit = None

        # Cache + verifier + sessions.
        try:
            from .cache.exact import ExactCache
            from .cache.semantic import SemanticCache

            self.exact_cache = ExactCache()
            self.semantic_cache = SemanticCache(store_text=True)
        except Exception:
            self.exact_cache = None
            self.semantic_cache = None
        try:
            from .core.verifier.base import VerifierPipeline

            self.verifier = VerifierPipeline()
        except Exception:
            self.verifier = None
        try:
            from .core.session import SessionManager

            self.sessions = SessionManager()
        except Exception:
            self.sessions = None

        self.performance.rebuild_from_memory()
        try:
            self.performance.set_models(self.models)
        except Exception:
            pass

    # -- New v1.1 SDK -----------------------------------------------------
    async def route(
        self,
        query: str,
        *,
        task_id=None,
        budget=None,
        trust_required=None,
        context=None,
    ) -> RouteResult:
        """Zero-API default path: features -> constraints -> cache -> bandit -> verify."""
        from .core.policy.engine import PolicyContext
        from .core.reward import compute_reward

        context = context or {}
        trust_required = trust_required or {}
        # Session / budget handling.
        session = None
        if (task_id is not None or budget is not None) and self.sessions is not None:
            try:
                session = None
                if task_id is not None:
                    session = self.sessions.get_by_task(task_id)
                if session is None:
                    session = self.sessions.create(task_id=task_id, budget=budget)
                elif budget is not None and session.budget is None:
                    session.budget = budget
            except Exception:
                session = None

        query_features = self.feature_extractor.extract(query)
        analysis = await self.analyzer.analyze(query)

        # Surface reasoning: learning_router returns (decision, reasoning).
        try:
            decision, reasoning = self.learning_router.route(
                analysis, query_features, trust_required=trust_required
            )
        except Exception as exc:
            # Fail-closed: no eligible candidate => refuse.
            from .core.trust import TrustViolation

            if isinstance(exc, TrustViolation) or "trust" in str(exc).lower():
                raise RuntimeError(f"Request refused: no model satisfies trust policy ({exc})")
            raise

        self.confidence_engine.threshold = self.adaptive_threshold.get_threshold()

        # Policy engine hard constraints (trust/budget/SLO/health/capability).
        constraints_applied: List[str] = list(decision.constraints_applied or [])
        candidates = [decision.model] + list(decision.alternatives or [])
        bandit_score = 0.0
        policy_ctx = PolicyContext(
            query_type=query_features.query_type.value,
            complexity=analysis.complexity,
            budget_remaining=(
                (session.budget - session.spent) if session and session.budget else None
            ),
            cost_ceiling=context.get("cost_ceiling"),
            latency_slo_ms=context.get("latency_slo_ms"),
            trust_required=trust_required,
            tenant_tier=str(context.get("tenant_tier", "default")),
            capabilities_needed=list(analysis.capabilities_needed or []),
            estimated_tokens_in=int(analysis.estimated_tokens or 100),
        )
        if self.policy_engine is not None:
            try:
                result = self.policy_engine.evaluate(candidates, policy_ctx)
                if not result.eligible:
                    if self.fail_closed:
                        raise RuntimeError(
                            "Request refused: policy excludes all candidates: "
                            + "; ".join(result.excluded)
                        )
                else:
                    candidates = result.eligible
                    decision.model = candidates[0]
                    decision.tier = decision.model.tier
                    constraints_applied = sorted(
                        set(constraints_applied)
                        | (["trust_policy"] if self.trust_policy or trust_required else [])
                        | (["budget"] if policy_ctx.budget_remaining is not None else [])
                        | (["latency_slo"] if policy_ctx.latency_slo_ms else [])
                    )
                    decision.constraints_applied = constraints_applied
                    # Attach penalties for bandit.
                    policy_ctx.penalties = result.penalties  # type: ignore
            except RuntimeError:
                raise
            except Exception:
                pass

        # Cache: exact -> semantic (miss => continue).
        cached = False
        cache_key = None
        tenant = _tenant_of(context)
        trust_hash = _trust_digest(trust_required)
        if self.exact_cache is not None:
            try:
                from .cache.exact import cache_key as _ck

                model_set_version = ",".join(sorted(m.name for m in self.models))
                cache_key = _ck(query, model_set_version, self.policy_version, tenant, trust_hash)
                hit = self.exact_cache.get(cache_key)
                if (
                    hit
                    and isinstance(hit, dict)
                    and hit.get("policy_version", "1") == self.policy_version
                ):
                    return self._result_from_cache(
                        hit,
                        decision,
                        reasoning,
                        query_features,
                        analysis,
                        query=query,
                        cache_key=cache_key,
                        trust_required=trust_required,
                        context=context,
                    )
            except Exception:
                pass
        if self.semantic_cache is not None and not cached:
            try:
                sem = self.semantic_cache.get(
                    query,
                    policy_version=self.policy_version,
                    tenant=tenant,
                    trust_hash=trust_hash,
                )
                if sem and sem.get("response"):
                    # Only use semantic hit when raw text storage is allowed.
                    hit = {
                        "response": sem["response"],
                        "model": sem.get("model", decision.model.name),
                        "policy_version": self.policy_version,
                    }
                    return self._result_from_cache(
                        hit,
                        decision,
                        reasoning,
                        query_features,
                        analysis,
                        query=query,
                        cache_key=cache_key,
                        trust_required=trust_required,
                        semantic=True,
                        context=context,
                    )
            except Exception:
                pass

        # Bandit selection among policy-eligible candidates.
        if self.bandit is not None and len(candidates) > 1:
            try:
                pick, score, _info = self.bandit.select(candidates, policy_ctx)
                decision.model = pick
                decision.tier = pick.tier
                bandit_score = float(score)
                decision.bandit_score = bandit_score
            except Exception:
                pass
        # Session coherence pin.
        if session is not None and getattr(session, "pinned_model", None):
            pinned = self.registry.get_model(session.pinned_model)
            if pinned is not None and pinned in candidates:
                decision.model = pinned
                decision.tier = pinned.tier

        # Decomposed path with real sub-query merge.
        if self.decompose_queries:
            sub_queries = self.decomposer.decompose(query, analysis)
            if len(sub_queries) > 1:
                return await self._route_decomposed_v11(
                    query,
                    query_features,
                    analysis,
                    decision,
                    reasoning,
                    sub_queries,
                    session=session,
                    trust_required=trust_required,
                    context=context,
                    cache_key=cache_key,
                    bandit_score=bandit_score,
                )

        # Budget pre-check (input + output estimate, tokens, calls, latency).
        if session is not None:
            try:
                est_tokens = int(policy_ctx.estimated_tokens_in or 0)
                est = (est_tokens / 1000) * (
                    decision.model.cost_per_1k_input + decision.model.cost_per_1k_output
                )
                ok, reason = session.check_allow(est_cost=est, est_tokens=est_tokens)
                if not ok:
                    degraded = True
                    if self.fail_closed:
                        raise RuntimeError(f"Request refused: session {reason}")
            except RuntimeError:
                raise
            except Exception:
                pass

        response, confidence, decision, fallback_total = await self._generate_and_check_v11(
            query,
            analysis,
            query_features,
            decision,
            trust_required=trust_required,
            eligible_names={m.name for m in candidates},
            policy_ctx=policy_ctx,
        )
        # Verifier gate (generic): fail => escalate once to safest trusted model.
        # Async path preferred so rubric judges actually execute.
        verifier_result = None
        if self.verifier is not None and getattr(self.verifier, "verifiers", []):
            try:
                averify_fn = getattr(self.verifier, "averify", None)
                if callable(averify_fn):
                    verifier_result = await averify_fn(query, response.content, context)
                else:
                    verifier_result = self.verifier.verify(query, response.content, context)
                if not verifier_result.passed:
                    esc = self._safest_trusted(candidates, trust_required)
                    if esc is not None and esc.name != decision.model.name:
                        provider = self.registry.get_provider(esc.name)
                        if provider is not None:
                            try:
                                response = await provider.generate(query)
                                if callable(averify_fn):
                                    verifier_result = await averify_fn(
                                        query, response.content, context
                                    )
                                else:
                                    verifier_result = self.verifier.verify(
                                        query, response.content, context
                                    )
                                decision = RoutingDecision(
                                    model=esc,
                                    tier=esc.tier,
                                    reason=f"Verifier escalated to safest trusted {esc.name}",
                                    alternatives=[],
                                    degraded=True,
                                    constraints_applied=constraints_applied,
                                )
                            except Exception:
                                pass
            except Exception:
                verifier_result = None

        # Fail-closed confidence escalation.
        degraded = bool(getattr(decision, "degraded", False) or confidence.degraded)
        if not confidence.is_confident and self.fail_closed:
            degraded = True
            # Escalate to safest trusted model if not already there.
            safest = self._safest_trusted(candidates, trust_required)
            if safest is not None and safest.name != decision.model.name:
                provider = self.registry.get_provider(safest.name)
                if provider is not None:
                    try:
                        esc_response = await provider.generate(query)
                        esc_conf = await self.confidence_engine.check(
                            query, esc_response, query_features=query_features
                        )
                        # Accept escalation even if still low (safest effort), mark degraded.
                        response = esc_response
                        confidence = esc_conf
                        decision = RoutingDecision(
                            model=safest,
                            tier=safest.tier,
                            reason=f"Fail-closed escalation to safest trusted {safest.name}",
                            alternatives=[],
                            degraded=True,
                            constraints_applied=constraints_applied,
                        )
                        degraded = True
                    except Exception:
                        pass

        # Predicted cost/latency.
        try:
            decision.predicted_cost = (
                response.tokens_in / 1000
            ) * decision.model.cost_per_1k_input + (
                response.tokens_out / 1000
            ) * decision.model.cost_per_1k_output
            decision.predicted_latency_ms = int(response.latency_ms)
            decision.cache_key = cache_key
        except Exception:
            pass

        # Reward + learning updates.
        cost = self._route_cost(response, decision.model, confidence)
        reward = 0.0
        try:
            reward = compute_reward(
                quality=float(confidence.score),
                cost=float(cost.actual_cost),
                latency_ms=int(response.latency_ms),
                verifier_pass=bool(verifier_result.passed) if verifier_result else True,
                fallback=bool(fallback_total > 0),
                retries=int(fallback_total),
            )
        except Exception:
            pass
        # Ledger append (hash-chained, signed) BEFORE the trace so the
        # persisted trace can link to its audit entry. A failed append
        # raises inside ledger.append and leaves ledger_id empty (honest).
        ledger_id = ""
        try:
            entry = self.ledger.append(
                {
                    "query": query[:500],
                    "model": decision.model.name,
                    "tier": decision.tier.value,
                    "confidence": confidence.score,
                    "consensus_score": getattr(confidence, "consensus_score", None),
                    "propensity": 1.0,
                    "cost": cost.actual_cost,
                    "degraded": degraded,
                    "policy_version": self.policy_version,
                }
            )
            ledger_id = f"{entry.get('seq', '')}:{entry.get('payload_hash', '')[:12]}"
        except Exception:
            pass
        self._finish_route_v11(
            query,
            query_features,
            analysis,
            decision,
            response,
            confidence,
            fallback_total,
            cost,
            reward,
            policy_ctx,
            degraded,
            ledger_id=ledger_id,
            trust_required=trust_required,
        )
        # OTel export (best-effort).
        try:
            from .tracking.otel import record_route as _otel_route

            _otel_route(
                query=query,
                model=decision.model.name,
                confidence=confidence.score,
                cost=cost.actual_cost,
                degraded=degraded,
            )
        except Exception:
            pass
        # Cache store. Privacy first: no_raw_cache skips ALL raw-response
        # persistence (exact SQLite and semantic), not just semantic.
        allow_text = True
        if isinstance(trust_required, dict) and trust_required.get("no_raw_cache"):
            allow_text = False
        try:
            if self.exact_cache is not None and cache_key and allow_text:
                self.exact_cache.put(
                    cache_key,
                    {
                        "response": response.content,
                        "model": decision.model.name,
                        "tier": decision.tier.value,
                        "policy_version": self.policy_version,
                    },
                )
            if self.semantic_cache is not None:
                if allow_text:
                    self.semantic_cache.put(
                        query,
                        response.content,
                        decision.model.name,
                        policy_version=self.policy_version,
                        tenant=tenant,
                        trust_hash=trust_hash,
                    )
        except Exception:
            pass
        if session is not None:
            try:
                session.record(
                    cost.actual_cost, response.tokens_in + response.tokens_out, response.latency_ms
                )
            except Exception:
                pass

        reasoning_full = self.reasoning_engine.explain(
            query=query,
            analysis=analysis,
            decision=decision,
            query_features=query_features,
            merged_reasoning=reasoning,
        )
        result = RouteResult(
            response=response.content,
            model=decision.model.name,
            tier=decision.tier.value,
            reasoning=reasoning_full,
            confidence=confidence,
            cost=cost,
            candidates=[m.name for m in candidates],
            degraded=degraded,
            cached=False,
            trust=decision.model.trust,
            verifier=verifier_result,
            ledger_id=ledger_id,
        )
        try:
            object.__setattr__(result, "_provider_response", response)
        except Exception:
            try:
                result._provider_response = response  # type: ignore
            except Exception:
                pass
        return result

    def explain(self, result: RouteResult) -> str:
        parts = [
            f"Model: {result.model} [{result.tier}]",
            f"Reasoning: {result.reasoning}",
            f"Confidence: {result.confidence.score:.2f} ({result.confidence.method})",
            f"Cost: ${result.cost.actual_cost:.4f} (baseline {result.cost.baseline_model})",
        ]
        if result.cached:
            parts.append("cached: true")
        if result.degraded:
            parts.append(
                f"degraded: true (confidence {result.confidence.score:.2f} "
                f"< {result.confidence.threshold:.2f})"
            )
        if result.verifier is not None:
            parts.append(
                f"verifier {result.verifier.verifier_name}: {'pass' if result.verifier.passed else 'fail'}"
            )
        if result.ledger_id:
            parts.append(f"ledger: {result.ledger_id}")
        return " | ".join(parts)

    def _safest_trusted(self, candidates: List[ModelConfig], trust_required=None):
        # Safest = highest safety_tier, then ZDR, then premium tier.
        from .core.trust import filter_by_trust

        eligible, _ = filter_by_trust(candidates, self.trust_policy, trust_required or {})
        if not eligible:
            return None
        order = {"standard": 0, "elevated": 1, "high": 2}

        def _key(m):
            return (
                order.get(getattr(m.trust, "safety_tier", "standard"), 0),
                1 if getattr(m.trust, "zdr", False) else 0,
                {"free": 0, "mid": 1, "premium": 2}.get(m.tier.value, 0),
            )

        return sorted(eligible, key=_key, reverse=True)[0]

    def _result_from_cache(
        self,
        hit: dict,
        decision,
        reasoning,
        query_features,
        analysis,
        query: str = "",
        cache_key=None,
        trust_required=None,
        semantic: bool = False,
        context: Optional[dict] = None,
    ) -> RouteResult:
        model_name = hit.get("model", decision.model.name)
        model = self.registry.get_model(model_name) or decision.model
        # Trust re-check: a hit cached under weaker requirements must not
        # satisfy a stricter request. Raised => caller treats as a miss.
        try:
            from .core.trust import filter_by_trust

            eligible, _ = filter_by_trust([model], self.trust_policy, trust_required or {})
            if not eligible:
                raise _CacheTrustMiss(f"cached model {model.name} fails current trust requirements")
        except _CacheTrustMiss:
            raise
        except Exception:
            pass
        # Policy re-check: cached model must still satisfy current budget,
        # cost, latency, capability, and health constraints.
        try:
            if self.policy_engine is not None:
                from .core.policy.engine import PolicyContext as _CachePolicyContext

                _ctx = context or {}
                _qtype = "general"
                try:
                    _qtype = query_features.query_type.value
                except Exception:
                    _qtype = "general"
                ctx = _CachePolicyContext(
                    query_type=_qtype,
                    complexity=float(getattr(analysis, "complexity", 0.0) or 0.0),
                    budget_remaining=None,
                    cost_ceiling=_ctx.get("cost_ceiling"),
                    latency_slo_ms=_ctx.get("latency_slo_ms"),
                    trust_required=trust_required or {},
                    tenant_tier=str(_ctx.get("tenant_tier", "default")),
                    capabilities_needed=list(getattr(analysis, "capabilities_needed", []) or []),
                    estimated_tokens_in=int(getattr(analysis, "estimated_tokens", 100) or 100),
                )
                res = self.policy_engine.evaluate([model], ctx)
                if not res.eligible:
                    raise _CacheTrustMiss(
                        f"cached model {model.name} fails current policy: {res.excluded}"
                    )
                if not self.health.allow(model.name):
                    raise _CacheTrustMiss(f"cached model {model.name} temporarily unhealthy")
        except _CacheTrustMiss:
            raise
        except Exception:
            pass
        content = hit.get("response", "")
        # Honest confidence for cache hits: high but marked.
        conf = ConfidenceResult(
            score=0.95,
            is_confident=True,
            threshold=self.confidence_engine.threshold,
            reasoning="Cache hit",
            calibrated=False,
            method="heuristic",
        )
        cost = CostAnalysis(
            actual_cost=0.0,
            would_have_cost=0.0,
            savings=0.0,
            savings_percentage=0.0,
            model_used=model.name,
            tier=model.tier.value,
            baseline_model=cost_baseline(self),
            aux_calls=0,
            aux_cost=0.0,
        )
        reasoning_full = (
            self.reasoning_engine.explain(
                query_features=query_features,
                analysis=analysis,
                decision=decision,
                query="",
                merged_reasoning=reasoning + " | cache hit",
            )
            if hasattr(self.reasoning_engine, "explain")
            else reasoning
        )
        pr = ProviderResponse(
            content=content,
            model_used=model.name,
            provider=model.provider,
            tokens_in=0,
            tokens_out=0,
            latency_ms=0,
        )
        result = RouteResult(
            response=content,
            model=model.name,
            tier=model.tier.value,
            reasoning=reasoning_full,
            confidence=conf,
            cost=cost,
            candidates=[model.name],
            degraded=False,
            cached=True,
            trust=model.trust,
            verifier=None,
            ledger_id="cache",
        )
        try:
            object.__setattr__(result, "_provider_response", pr)
        except Exception:
            pass
        # Cache-hit accounting: zero-cost trace + ledger event so lifetime
        # stats include served-from-cache requests (never a provider outcome:
        # no memory/performance/bandit updates here).
        try:
            tracking = self.config.get_tracking_config()
            if tracking.get("log_queries", True):
                ledger_id = ""
                try:
                    entry = self.ledger.append(
                        {
                            "query": (query or "")[:500],
                            "model": model.name,
                            "tier": model.tier.value,
                            "confidence": conf.score,
                            "cost": 0.0,
                            "cache_hit": True,
                            "policy_version": self.policy_version,
                        }
                    )
                    ledger_id = f"{entry.get('seq', '')}:{entry.get('payload_hash', '')[:12]}"
                except Exception:
                    pass
                try:
                    self.trace_logger.log(
                        query=query or "",
                        analysis=analysis,
                        decision=decision,
                        response=pr,
                        confidence=conf,
                        cost=cost,
                        cache_hit=True,
                        ledger_id=ledger_id or None,
                        policy_version=self.policy_version,
                    )
                except Exception:
                    pass
                try:
                    self.hop_score.update(is_optimal_hop(True, 0.0, 0.0))
                except Exception:
                    pass
                if ledger_id:
                    result.ledger_id = ledger_id
        except Exception:
            pass
        return result

    async def _generate_and_check_v11(
        self,
        query,
        analysis,
        query_features,
        decision,
        trust_required=None,
        eligible_names=None,
        policy_ctx=None,
    ):
        # Zero-API default: no provider passed to confidence; no consensus unless enabled.
        budget = self.fallback.max_retries + 1
        attempts = 0
        tried = {decision.model.name}
        current = decision
        best = None
        all_aux: List[ProviderResponse] = []
        # Health-gated candidates.
        while attempts < budget:
            # Circuit-breaker skip.
            try:
                if not self.health.allow(current.model.name):
                    nxt = self._next_fallback_decision(
                        current, tried, analysis, eligible_names, policy_ctx
                    )
                    if nxt is None:
                        break
                    current = nxt
                    tried.add(nxt.model.name)
                    continue
            except Exception:
                pass
            provider = self.registry.get_provider(current.model.name)
            attempts += 1
            if provider is None:
                nxt = self._next_fallback_decision(
                    current, tried, analysis, eligible_names, policy_ctx
                )
                if nxt is None:
                    break
                current = nxt
                tried.add(nxt.model.name)
                continue
            try:
                response = await provider.generate(query)
                try:
                    self.health.record_success(current.model.name, response.latency_ms)
                except Exception:
                    pass
            except Exception as exc:
                try:
                    self.health.record_failure(current.model.name, exc)
                except Exception:
                    pass
                nxt = self._next_fallback_decision(
                    current, tried, analysis, eligible_names, policy_ctx
                )
                if nxt is None:
                    break
                current = nxt
                tried.add(nxt.model.name)
                continue
            # Zero-aux default: no provider/consensus passed.
            if self.enable_consensus:
                confidence = await self.confidence_engine.check(
                    query,
                    response,
                    provider=None,
                    consensus_provider=(
                        self._get_consensus_provider(current.model.name)
                        if self.enable_consensus
                        else None
                    ),
                    query_features=query_features,
                )
                # Aux accounting flows through _route_cost -> calculate
                # (single counting point); no separate record_aux here.
            else:
                confidence = await self.confidence_engine.check(
                    query,
                    response,
                    provider=None,
                    consensus_provider=None,
                    query_features=query_features,
                )
            all_aux.extend(confidence.auxiliary_responses)
            if confidence.is_confident:
                confidence = confidence.model_copy(update={"auxiliary_responses": all_aux})
                return response, confidence, current, attempts - 1
            best = (current, response, confidence)
            nxt = self._next_fallback_decision(current, tried, analysis, eligible_names, policy_ctx)
            if nxt is None:
                break
            current = nxt
            tried.add(nxt.model.name)
        if best is not None:
            current, response, confidence = best
            confidence = confidence.model_copy(update={"auxiliary_responses": all_aux})
            return response, confidence, current, attempts - 1
        raise RuntimeError(
            f"No provider could handle the query after {self.fallback.max_retries} retries"
        )

    async def _route_decomposed_v11(
        self,
        query,
        query_features,
        analysis,
        parent_decision,
        reasoning,
        sub_queries,
        session=None,
        trust_required=None,
        context=None,
        cache_key=None,
        bandit_score=0.0,
    ) -> RouteResult:
        responses = []
        confidences = []
        costs = []
        fallback_used = False
        total_fallback = 0
        total_latency = 0
        tokens_in = 0
        tokens_out = 0
        perf_records = []
        failed_parts = []
        tracking = self.config.get_tracking_config()
        log_queries = tracking.get("log_queries", True)
        for sub in sub_queries:
            try:
                sub_features = self.feature_extractor.extract(sub.query)
                sub_decision, _ = self.learning_router.route(
                    sub.analysis, sub_features, trust_required=trust_required or {}
                )
                self.confidence_engine.threshold = self.adaptive_threshold.get_threshold()
                # Policy-vet the sub-decision like the parent route: same
                # budget/latency/trust/health gates, sub-query capabilities.
                # Capability *coverage* stays best-effort (the router owns it):
                # heuristic vocabularies routinely exceed config vocabularies
                # (e.g. "technical"), and refusing those would break
                # decomposition. Safety gates remain hard.
                from .core.policy.engine import (
                    CapabilityConstraint as _CapConstraint,
                )
                from .core.policy.engine import PolicyContext as _SubPolicyContext
                from .core.policy.engine import PolicyEngine as _SubPolicyEngine

                sub_vet_engine = self.policy_engine
                try:
                    if sub_vet_engine is not None:
                        keep = [
                            c
                            for c in sub_vet_engine.constraints
                            if not isinstance(c, _CapConstraint)
                        ]
                        if len(keep) != len(sub_vet_engine.constraints):
                            sub_vet_engine = _SubPolicyEngine(
                                constraints=keep,
                                policy_version=sub_vet_engine.policy_version,
                            )
                except Exception:
                    sub_vet_engine = self.policy_engine

                sub_ctx = _SubPolicyContext(
                    query_type=sub_features.query_type.value,
                    complexity=sub.analysis.complexity,
                    budget_remaining=(
                        (session.budget - session.spent)
                        if session is not None and session.budget
                        else None
                    ),
                    cost_ceiling=(context or {}).get("cost_ceiling"),
                    latency_slo_ms=(context or {}).get("latency_slo_ms"),
                    trust_required=trust_required or {},
                    tenant_tier=str((context or {}).get("tenant_tier", "default")),
                    capabilities_needed=list(sub.analysis.capabilities_needed or []),
                    estimated_tokens_in=int(sub.analysis.estimated_tokens or 100),
                )
                sub_eligible_names = None
                if sub_vet_engine is not None:
                    sub_cands = [sub_decision.model] + list(
                        getattr(sub_decision, "alternatives", []) or []
                    )
                    sub_res = sub_vet_engine.evaluate(sub_cands, sub_ctx)
                    if not sub_res.eligible:
                        if self.fail_closed:
                            raise RuntimeError(
                                "Sub-query refused: policy excludes all candidates: "
                                + "; ".join(sub_res.excluded)
                            )
                        sub_decision = RoutingDecision(
                            model=parent_decision.model,
                            tier=parent_decision.tier,
                            reason="Policy fallback to parent model",
                            alternatives=[],
                        )
                    else:
                        sub_decision = RoutingDecision(
                            model=sub_res.eligible[0],
                            tier=sub_res.eligible[0].tier,
                            reason=sub_decision.reason,
                            alternatives=sub_res.eligible[1:],
                        )
                        sub_eligible_names = {m.name for m in sub_res.eligible}
                resp, conf, final_decision, fb = await self._generate_and_check_v11(
                    sub.query,
                    sub.analysis,
                    sub_features,
                    sub_decision,
                    trust_required=trust_required,
                    eligible_names=sub_eligible_names,
                    policy_ctx=sub_ctx,
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
                costs.append(self._route_cost(resp, final_decision.model, conf))
            except Exception as exc:
                failed_parts.append(f"'{sub.query}' (purpose: {sub.purpose or 'complete'}): {exc}")
                continue
        if failed_parts:
            raise RuntimeError(
                f"Some sub-queries for '{query}' failed: " + " | ".join(failed_parts)
            )
        if not responses:
            raise RuntimeError(f"All sub-queries for '{query}' failed")
        # Real sub-query merge.
        composite_text = self.decomposer.synthesize(responses)
        composite = ProviderResponse(
            content=composite_text,
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
            method="heuristic",
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
            baseline = costs[0].baseline_model if costs else cost_baseline(self)
            cost = CostAnalysis(
                actual_cost=actual,
                would_have_cost=would,
                savings=would - actual,
                savings_percentage=(would - actual) / would * 100 if would > 0 else 0,
                model_used="decomposed",
                tier=parent_decision.tier.value,
                baseline_model=baseline,
                tokens_in=int(sum(c.tokens_in for c in costs)),
                tokens_out=int(sum(c.tokens_out for c in costs)),
            )
        else:
            cost = estimate_cost(
                composite,
                parent_decision.model,
                price_book=getattr(self.cost_tracker, "price_book", None),
                all_models=self.models,
            )
        ledger_id = ""
        if log_queries:
            try:
                entry = self.ledger.append(
                    {
                        "query": query[:500],
                        "model": "decomposed",
                        "tier": parent_decision.tier.value,
                        "confidence": composite_confidence.score,
                        "consensus_score": getattr(composite_confidence, "consensus_score", None),
                        "propensity": 1.0,
                        "cost": cost.actual_cost,
                        "degraded": bool(
                            getattr(parent_decision, "degraded", False)
                            or not composite_confidence.is_confident
                        ),
                        "policy_version": self.policy_version,
                    }
                )
                ledger_id = f"{entry.get('seq','')}:{entry.get('payload_hash','')[:12]}"
            except Exception:
                pass
            allow_text = not (
                isinstance(trust_required, dict) and trust_required.get("no_raw_cache")
            )
            trace = self.trace_logger.log(
                query=query,
                analysis=analysis,
                decision=parent_decision,
                response=composite,
                confidence=composite_confidence,
                cost=cost,
                fallback_count=total_fallback,
                ledger_id=ledger_id or None,
                allow_text=allow_text,
            )
            self.shield.check_quality(trace)
            self.hop_score.update(
                is_optimal_hop(
                    composite_confidence.is_confident, cost.savings, cost.would_have_cost
                )
            )
        # Session accounting for decomposed aggregates (budget/calls/tokens/latency).
        decomposed_degraded = bool(
            getattr(parent_decision, "degraded", False) or not composite_confidence.is_confident
        )
        if session is not None:
            try:
                ok, reason = session.check_allow(
                    est_cost=float(cost.actual_cost),
                    est_tokens=int(tokens_in + tokens_out),
                )
                if not ok and self.fail_closed:
                    raise RuntimeError(f"Request refused: session {reason}")
                if not ok:
                    decomposed_degraded = True
            except RuntimeError:
                raise
            except Exception:
                pass
            try:
                session.record(
                    float(cost.actual_cost),
                    int(tokens_in + tokens_out),
                    int(total_latency),
                )
            except Exception:
                pass
        # Cache population for decomposed responses (privacy-gated).
        try:
            allow_text = not (
                isinstance(trust_required, dict) and trust_required.get("no_raw_cache")
            )
            if allow_text:
                tenant = _tenant_of(context or {})
                trust_hash = _trust_digest(trust_required)
                if self.exact_cache is not None and cache_key:
                    self.exact_cache.put(
                        cache_key,
                        {
                            "response": composite_text,
                            "model": "decomposed",
                            "tier": parent_decision.tier.value,
                            "policy_version": self.policy_version,
                        },
                    )
                if self.semantic_cache is not None:
                    self.semantic_cache.put(
                        query,
                        composite_text,
                        "decomposed",
                        policy_version=self.policy_version,
                        tenant=tenant,
                        trust_hash=trust_hash,
                    )
        except Exception:
            pass
        reasoning_full = self.reasoning_engine.explain(
            query=query,
            analysis=analysis,
            decision=parent_decision,
            query_features=query_features,
            merged_reasoning=reasoning,
        )
        result = RouteResult(
            response=composite_text,
            model="decomposed",
            tier=parent_decision.tier.value,
            reasoning=reasoning_full,
            confidence=composite_confidence,
            cost=cost,
            candidates=[],
            degraded=decomposed_degraded,
            cached=False,
            trust=parent_decision.model.trust,
            verifier=None,
            ledger_id=ledger_id,
        )
        try:
            object.__setattr__(result, "_provider_response", composite)
        except Exception:
            pass
        return result

    # -- Backward-compat helpers (1.0.x callers) ---------------------------
    async def _generate_and_check(self, query, analysis, query_features, decision):
        return await self._generate_and_check_v11(query, analysis, query_features, decision)

    async def _route_decomposed(
        self, query, query_features, analysis, parent_decision, sub_queries
    ):
        # Legacy returns ProviderResponse for old callers.
        result = await self._route_decomposed_v11(
            query, query_features, analysis, parent_decision, "", sub_queries
        )
        try:
            return result._provider_response or ProviderResponse(
                content=result.response, model_used=result.model, provider="decomposed"
            )
        except Exception:
            return ProviderResponse(
                content=result.response, model_used=result.model, provider="decomposed"
            )

    def _finish_route(
        self, query, query_features, analysis, decision, response, confidence, fallback_count
    ) -> None:
        cost = self._route_cost(response, decision.model, confidence)
        self._finish_route_v11(
            query,
            query_features,
            analysis,
            decision,
            response,
            confidence,
            fallback_count,
            cost,
            0.0,
            None,
            bool(getattr(decision, "degraded", False)),
        )

    def _finish_route_v11(
        self,
        query,
        query_features,
        analysis,
        decision,
        response,
        confidence,
        fallback_count,
        cost,
        reward,
        policy_ctx,
        degraded,
        ledger_id: str = "",
        trust_required: Optional[dict] = None,
    ) -> None:
        tracking = self.config.get_tracking_config()
        log_queries = tracking.get("log_queries", True)
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
            # Bandit + calibration learning loop.
            try:
                if self.bandit is not None and policy_ctx is not None:
                    self.bandit.update(decision.model, policy_ctx, reward)
                    if self._store is not None:
                        self.bandit.save(self._store)
            except Exception:
                pass
        if log_queries:
            allow_text = not (
                isinstance(trust_required, dict) and trust_required.get("no_raw_cache")
            )
            trace = self.trace_logger.log(
                query=query,
                analysis=analysis,
                decision=decision,
                response=response,
                confidence=confidence,
                cost=cost,
                fallback_count=fallback_count,
                degraded=degraded,
                ledger_id=ledger_id or None,
                policy_version=self.policy_version,
                allow_text=allow_text,
            )
            self.shield.check_quality(trace)
            self.hop_score.update(
                is_optimal_hop(confidence.is_confident, cost.savings, cost.would_have_cost)
            )

    def _get_consensus_provider(self, exclude_model: str):
        for name, provider in self.registry.get_available_providers().items():
            if name != exclude_model:
                return provider
        return None

    def _next_fallback_decision(
        self,
        current_decision,
        tried_models,
        analysis=None,
        eligible_names=None,
        policy_ctx=None,
    ):
        """Next fallback restricted to the request's approved set.

        Walks the cascade past models excluded by the policy-eligible set
        and re-evaluates each candidate through the live policy context
        (budget/latency/health). Rejections are added to the caller's tried
        set. Returns None when nothing eligible remains.
        """
        available = set(self.registry.get_available_providers())
        tried = tried_models if isinstance(tried_models, set) else set(tried_models or [])
        origin = current_decision.model.name
        current_model = current_decision.model
        while True:
            model = self.fallback.next_candidate(current_model, analysis, tried, available)
            if model is None:
                return None
            tried.add(model.name)
            current_model = model
            if eligible_names is not None and model.name not in eligible_names:
                continue
            if policy_ctx is not None and self.policy_engine is not None:
                try:
                    res = self.policy_engine.evaluate([model], policy_ctx)
                except Exception:
                    continue
                if not res.eligible:
                    continue
            return RoutingDecision(
                model=model,
                tier=model.tier,
                reason=f"Fallback from {origin}",
                alternatives=[],
            )

    def _resolve_cost_model(self, name: str, fallback: ModelConfig) -> ModelConfig:
        model = self.registry.get_model(name)
        if model is not None:
            return model
        for candidate in self.models:
            if candidate.model == name:
                return candidate
        return fallback

    def _confidence_aux_cost(self, confidence: ConfidenceResult, model: ModelConfig):
        extra_actual = 0.0
        extra_would = 0.0
        extra_count = 0
        for aux in confidence.auxiliary_responses:
            aux_model = self._resolve_cost_model(aux.model_used, model)
            aux_cost = estimate_cost(
                aux,
                aux_model,
                price_book=getattr(self.cost_tracker, "price_book", None),
                all_models=self.models,
            )
            extra_actual += aux_cost.actual_cost
            extra_would += aux_cost.would_have_cost
            extra_count += 1
        return extra_actual, extra_would, extra_count

    def _route_cost(self, response, model, confidence) -> CostAnalysis:
        extra_actual, extra_would, extra_count = self._confidence_aux_cost(confidence, model)
        if self.config.get_tracking_config().get("log_costs", True):
            return self.cost_tracker.calculate(
                response,
                model,
                extra_actual=extra_actual,
                extra_would=extra_would,
                extra_aux_calls=extra_count,
            )
        base = estimate_cost(
            response,
            model,
            price_book=getattr(self.cost_tracker, "price_book", None),
            all_models=self.models,
        )
        total_actual = base.actual_cost + extra_actual
        total_would = base.would_have_cost + extra_would
        savings = total_would - total_actual
        return CostAnalysis(
            actual_cost=total_actual,
            would_have_cost=total_would,
            savings=savings,
            savings_percentage=(savings / total_would * 100) if total_would > 0 else 0,
            model_used=model.name,
            tier=model.tier.value,
            baseline_model=base.baseline_model,
            tokens_in=int(getattr(response, "tokens_in", 0) or 0),
            tokens_out=int(getattr(response, "tokens_out", 0) or 0),
        )


def cost_baseline(mh) -> str:
    try:
        book = getattr(getattr(mh, "cost_tracker", None), "price_book", None)
        models = getattr(mh, "models", [])
        if book is not None and models:
            return book.baseline_model_name(models)
    except Exception:
        pass
    return ""


__all__ = [
    "ModelHop",
    "Config",
    "Tier",
    "ComplexityLevel",
    "EmotionalTone",
    "ModelConfig",
    "TrustProfile",
    "QueryAnalysis",
    "RoutingDecision",
    "RouteResult",
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
    "PerformanceCard",
    "ModelProfile",
    "SubQuery",
    "VerifierResult",
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
    "PriceBook",
    "estimate_cost",
    "TraceLogger",
    "DecisionLedger",
    "HopScore",
    "is_optimal_hop",
    "Shield",
    "Hub",
]
