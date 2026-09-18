from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Tier(str, Enum):
    FREE = "free"
    MID = "mid"
    PREMIUM = "premium"


class ComplexityLevel(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class EmotionalTone(str, Enum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    URGENT = "urgent"
    ANGRY = "angry"


class TrustProfile(BaseModel):
    data_classes: List[str] = Field(default_factory=lambda: ["general"])
    max_sensitivity: str = "public"  # public|internal|confidential|restricted
    zdr: bool = False
    jurisdiction: Optional[str] = None
    safety_tier: str = "standard"  # standard|elevated|high


class ModelConfig(BaseModel):
    name: str
    provider: str
    model: str
    tier: Tier
    capabilities: List[str] = Field(default_factory=list)
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_tokens: int = 4096
    avg_latency_ms: int = 500
    api_key_env: str = ""
    trust: TrustProfile = Field(default_factory=TrustProfile)
    context_window: int = 0
    supports_tools: bool = False
    supports_streaming: bool = True
    timeout_s: float = 30.0
    max_retries: int = 2
    price_effective_date: Optional[str] = None


class QueryAnalysis(BaseModel):
    complexity: float = Field(ge=0.0, le=1.0)
    level: ComplexityLevel
    capabilities_needed: List[str] = Field(default_factory=list)
    emotional_tone: EmotionalTone = EmotionalTone.NEUTRAL
    estimated_tokens: int = 100
    reasoning: str = ""


class RoutingDecision(BaseModel):
    model: ModelConfig
    tier: Tier
    reason: str
    alternatives: List[ModelConfig] = Field(default_factory=list)
    degraded: bool = False
    constraints_applied: List[str] = Field(default_factory=list)
    bandit_score: float = 0.0
    predicted_cost: float = 0.0
    predicted_latency_ms: int = 0
    cache_key: Optional[str] = None


class ProviderResponse(BaseModel):
    content: str
    model_used: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raw_response: Optional[Any] = Field(default=None, exclude=True)


class ConfidenceResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    is_confident: bool
    threshold: float
    consensus_model: Optional[str] = None
    consensus_score: Optional[float] = None
    reasoning: str = ""
    auxiliary_responses: List[ProviderResponse] = Field(default_factory=list)
    calibrated: bool = False
    method: str = "heuristic"  # heuristic|calibrated|consensus
    ece: Optional[float] = None
    degraded: bool = False


class CostAnalysis(BaseModel):
    actual_cost: float
    would_have_cost: float
    savings: float
    savings_percentage: float
    model_used: str
    tier: str
    baseline_model: str = ""
    aux_calls: int = 0
    aux_cost: float = 0.0
    currency: str = "USD"
    tokens_in: int = 0
    tokens_out: int = 0


class TraceEntry(BaseModel):
    query_id: str
    query: str
    timestamp: datetime
    analysis: QueryAnalysis
    decision: RoutingDecision
    response: ProviderResponse
    confidence: ConfidenceResult
    cost: CostAnalysis
    fallback_used: bool = False
    fallback_count: int = 0
    total_latency_ms: int = 0
    ledger_id: Optional[str] = None
    cache_hit: bool = False
    degraded: bool = False
    policy_version: str = "1"


class VerifierResult(BaseModel):
    verifier_name: str
    passed: bool
    score: float = 0.0
    details: dict = Field(default_factory=dict)


class PerformanceCard(BaseModel):
    schema_version: int = 1
    model: str
    query_type: str
    sample_count: int
    avg_quality: float
    avg_latency_ms: int
    fallback_rate: float
    region: Optional[str] = None
    mac: str = ""


class RouteResult(BaseModel):
    response: str
    model: str
    tier: str
    reasoning: str = ""
    confidence: ConfidenceResult
    cost: CostAnalysis
    candidates: list = Field(default_factory=list)
    degraded: bool = False
    cached: bool = False
    trust: TrustProfile = Field(default_factory=TrustProfile)
    verifier: Optional[VerifierResult] = None
    ledger_id: str = ""

    model_config = {"arbitrary_types_allowed": True}

    # Backward-compat bridge (not a serialized field).
    _provider_response: Optional[ProviderResponse] = None  # type: ignore

    @property
    def content(self) -> str:
        return self.response

    @property
    def model_used(self) -> str:
        return self.model

    @property
    def provider(self) -> str:
        if self._provider_response is not None:
            return self._provider_response.provider
        return ""

    @property
    def tokens_in(self) -> int:
        if self._provider_response is not None:
            return self._provider_response.tokens_in
        return 0

    @property
    def tokens_out(self) -> int:
        if self._provider_response is not None:
            return self._provider_response.tokens_out
        return 0

    @property
    def latency_ms(self) -> int:
        if self._provider_response is not None:
            return self._provider_response.latency_ms
        return 0


class HopScoreResult(BaseModel):
    score: int = Field(ge=0, le=100)
    total_queries: int
    optimal_routes: int
    rating: str


class ShieldStatus(BaseModel):
    active: bool
    quality_score: float
    consensus_rate: float
    alerts: List[str] = Field(default_factory=list)
    adjustments_today: int = 0


class QueryType(str, Enum):
    IMPLEMENTATION = "implementation"
    EXPLANATION = "explanation"
    DEBUGGING = "debugging"
    COMPARISON = "comparison"
    CREATIVE = "creative"
    GENERAL = "general"


class QueryFeatures(BaseModel):
    length: int = 0
    has_code_block: bool = False
    has_question: bool = False
    technical_term_ratio: float = 0.0
    code_keyword_count: int = 0
    algorithm_term_count: int = 0
    complexity_term_count: int = 0
    is_implementation: bool = False
    is_explanation: bool = False
    is_debugging: bool = False
    is_comparison: bool = False
    is_creative: bool = False
    has_constraints: bool = False
    requires_optimization: bool = False
    multi_step: bool = False
    query_type: QueryType = QueryType.GENERAL
    feature_vector: List[float] = Field(default_factory=list)


class SubQuery(BaseModel):
    query: str
    analysis: QueryAnalysis
    purpose: str = ""


class SubQueryResponse(BaseModel):
    sub_query: SubQuery
    response: ProviderResponse
    model_used: str = ""


class Experience(BaseModel):
    query_id: str = ""
    query: str = ""
    query_features: Optional[QueryFeatures] = None
    analysis: Optional[QueryAnalysis] = None
    decision: Optional[RoutingDecision] = None
    response_quality: float = 0.0
    fallback_used: bool = False
    model_name: str = ""
    tier: str = ""
    query_type: QueryType = QueryType.GENERAL
    latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class PerformanceMetrics(BaseModel):
    sample_count: int = 0
    weight_sum: float = 0.0
    avg_quality: float = 0.0
    quality_stddev: float = 0.0
    avg_latency_ms: int = 0
    fallback_rate: float = 0.0
    success_rate: float = 1.0


class ModelProfile(BaseModel):
    name: str = ""
    provider: str = ""
    tier: Tier = Tier.FREE
    static_capabilities: List[str] = Field(default_factory=list)
    performance_by_query_type: dict = Field(default_factory=dict)
    overall_quality: float = 0.5
    avg_latency_ms: int = 500
    quality_variance: float = 0.1


class HubConfig(BaseModel):
    name: str
    author: str
    description: str
    rating: float
    downloads: int
    tags: List[str] = Field(default_factory=list)
    yaml_content: str
