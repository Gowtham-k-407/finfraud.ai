from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskContribution(BaseModel):
    factor: str
    score: float
    weight: float
    weighted_points: float
    detail: str


class EvidenceItem(BaseModel):
    evidence_id: str
    category: str  # FACT_TRANSACTION | FACT_INFRASTRUCTURE | ANALYTICAL_PATTERN | ML_ANOMALY
    title: str
    description: str
    is_direct_fact: bool = True
    confidence: str = "HIGH"  # HIGH | MEDIUM | LOW
    related_entities: List[str] = Field(default_factory=list)
    supporting_transactions: List[str] = Field(default_factory=list)
    timestamp: Optional[str] = None
    amount: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatternDetection(BaseModel):
    detection_id: str
    pattern_type: str  # FAN_IN | FAN_OUT | RAPID_PASS_THROUGH | CIRCULAR_FLOW | SHARED_DEVICE | SHARED_IP | MULE_ACCOUNT_INDICATOR | BEHAVIORAL_ANOMALY
    pattern_label: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    risk_score: float
    primary_entity: str
    involved_entities: List[str]
    supporting_transactions: List[str]
    total_amount: float = 0.0
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None
    duration_minutes: Optional[float] = None
    summary: str
    explanation: str
    alternative_explanations: List[str] = Field(default_factory=list)
    confidence_basis: str
    data_source: str = "hybrid"
    is_synthetic_scenario: bool = False
    scenario_tag: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class HypothesisEvaluation(BaseModel):
    hypothesis_id: str
    title: str
    category: str  # SUSPICIOUS_TYPOLOGY | BENIGN_ALTERNATIVE
    description: str
    confidence: str  # HIGH | MODERATE | LOW
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    missing_evidence: List[str]
    recommended_next_step: str
    analyst_verdict: Optional[str] = None  # None | USEFUL | REJECTED


class InvestigationReport(BaseModel):
    investigation_id: str
    target_id: str
    target_type: str  # ACCOUNT | DETECTION | TRANSACTION
    created_at: str
    generation_mode: str  # llm_grounded | deterministic_evidence_engine
    llm_provider: Optional[str] = None
    overall_priority: str  # CRITICAL | HIGH | MEDIUM | LOW
    composite_risk_score: float
    executive_summary: str
    involved_entities: List[str]
    suspicious_paths: List[List[str]] = Field(default_factory=list)
    supporting_transactions: List[str] = Field(default_factory=list)
    total_volume_analyzed: float = 0.0
    currency: str = "USD"
    time_span: Dict[str, Optional[str]] = Field(default_factory=dict)
    verified_facts: List[EvidenceItem] = Field(default_factory=list)
    analytical_inferences: List[str] = Field(default_factory=list)
    hypotheses: List[HypothesisEvaluation] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)
    evidence_limitations: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    data_provenance_note: str = ""
    notes: List[Dict[str, Any]] = Field(default_factory=list)


class DatasetProcessRequest(BaseModel):
    source_mode: str = "hybrid"  # hybrid | kaggle_only | synthetic_only | custom_csv
    max_kaggle_rows: int = Field(default=10000, ge=500, le=200000)
    include_synthetic_scenarios: bool = True


class InvestigationCreateRequest(BaseModel):
    target_id: str
    target_type: str = "ACCOUNT"  # ACCOUNT | DETECTION | TRANSACTION
    use_llm_if_available: bool = True


class NoteCreateRequest(BaseModel):
    author: str = "Senior AML Analyst"
    content: str
    hypothesis_id: Optional[str] = None
    verdict: Optional[str] = None  # USEFUL | REJECTED


class CaseCreateRequest(BaseModel):
    title: str
    primary_entity: str
    priority: str = "HIGH"
    assigned_analyst: str = "A. Sharma (FIU)"
    investigation_id: Optional[str] = None
    detection_ids: List[str] = Field(default_factory=list)
    summary: str = ""


class CaseUpdateRequest(BaseModel):
    status: Optional[str] = None  # OPEN | IN_REVIEW | ESCALATED | CLOSED_BENIGN
    priority: Optional[str] = None
    assigned_analyst: Optional[str] = None
    note: Optional[str] = None

