from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


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


class ProviderResponse(BaseModel):
    content: str
    model_used: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raw_response: Optional[Any] = None


class ConfidenceResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    is_confident: bool
    threshold: float
    consensus_model: Optional[str] = None
    consensus_score: Optional[float] = None
    reasoning: str = ""


class CostAnalysis(BaseModel):
    actual_cost: float
    would_have_cost: float
    savings: float
    savings_percentage: float
    model_used: str
    tier: str


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
