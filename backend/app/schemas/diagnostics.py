from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class DiagnosticEventRead(BaseModel):
    id: str
    scenario_id: str
    started_at: str
    ended_at: str
    rule_id: str
    severity: str
    evidence_json: Optional[Dict[str, Any]] = None
    conclusion_type: str
    generated_by_version: str

    model_config = ConfigDict(from_attributes=True)

class RuleRunRequest(BaseModel):
    scenario_id: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class RuleRunResponse(BaseModel):
    scenario_id: str
    algorithm_type: str = "RULE_BASELINE"
    events_found: int
    events: List[DiagnosticEventRead]

class DetectionSummary(BaseModel):
    status: str  # NORMAL, ANOMALY, INSUFFICIENT_DATA, OUT_OF_DOMAIN
    method: str  # RESIDUAL, MULTIVARIATE_PHYSICS, RULE
    observed_at: Optional[str] = None
    score: Optional[float] = None
    threshold: Optional[float] = None
    unit: str = "degC"
    alarm_minutes: int = 0
    alarm_episodes_count: int = 0
    operating_minutes: int = 0

class SensorProfileItem(BaseModel):
    id: str
    display_name: str
    description: str
    allowed_channels: List[str]
    has_valve_feedback: bool
    has_damper_feedback: bool
    version: str = "v1"
    channel_count: int

class LocalizationSummary(BaseModel):
    status: str  # PRELIMINARY_CLASS, UNRESOLVED, FAULT_FREE, NOT_EVALUATED, SINGLE_CAUSE, MULTIPLE_PLAUSIBLE
    candidate_class: Optional[str] = None
    candidate_class_ru: Optional[str] = None
    score: Optional[float] = None
    score_type: str = "uncalibrated_model_score"
    supporting_evidence: List[str] = []
    missing_evidence: List[str] = []
    limitations: List[str] = []
    # Stage 4 Decision Layer extensions:
    decision_status: Optional[str] = None  # SINGLE_CAUSE, MULTIPLE_PLAUSIBLE, CAUSE_UNRESOLVED, NO_ANOMALY, etc.
    single_cause: Optional[str] = None
    single_cause_ru: Optional[str] = None
    candidate_causes: List[str] = []
    reason_codes: List[str] = []
    structured_evidence: List[Dict[str, Any]] = []
    missing_measurements: List[str] = []

class DiagnosticProvenance(BaseModel):
    dataset_version: str
    model_id: str
    model_version: str
    threshold_policy: str
    feature_profile: str = "BASIC"
    scientific_disclaimer: str

class GroundTruthEvaluationInfo(BaseModel):
    source_fault_label: Optional[str] = None
    source_fault_label_type: Optional[str] = None
    description: Optional[str] = None
    is_benchmark_evaluation: bool = False

class ScenarioDiagnosticSummary(BaseModel):
    scenario_id: str
    scenario_name: str
    source_kind: str  # SIMULATED_BENCHMARK, SYNTHETIC_DEMO, USER_UPLOADED
    model_domain_status: str  # VALIDATED_ON_LBNL, OUT_OF_DOMAIN_UNVALIDATED, NOT_VALIDATED
    domain_warning: Optional[str] = None
    profile_id: str = "BASIC"
    profile_info: Optional[SensorProfileItem] = None
    detection: DetectionSummary
    localization: LocalizationSummary
    provenance: DiagnosticProvenance
    ground_truth: Optional[GroundTruthEvaluationInfo] = None
