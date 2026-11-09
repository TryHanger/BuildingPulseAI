from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class AdaptationStatus(str, Enum):
    OUT_OF_DOMAIN_UNVALIDATED = "OUT_OF_DOMAIN_UNVALIDATED"
    ADAPTATION_EXPERIMENTAL = "ADAPTATION_EXPERIMENTAL"
    LOCALLY_EVALUATED = "LOCALLY_EVALUATED"
    INSUFFICIENT_LOCAL_DATA = "INSUFFICIENT_LOCAL_DATA"
    INCOMPATIBLE_SENSOR_SEMANTICS = "INCOMPATIBLE_SENSOR_SEMANTICS"

class PredictionValidity(str, Enum):
    REGRESSION_ONLY_HELDOUT = "REGRESSION_ONLY_HELDOUT"
    NOT_VALIDATED = "NOT_VALIDATED"
    EXPERIMENTAL = "EXPERIMENTAL"

class TargetDatasetInfo(BaseModel):
    target_id: str
    name: str
    building_location: str
    facility_type: str
    source_kind: str
    scenario_id: str
    available_channels: List[str]
    normal_operating_minutes: int
    fault_episodes_count: int
    domain_guard_default: bool
    status: AdaptationStatus

class AdaptationModelCard(BaseModel):
    model_id: str
    name: str
    strategy_code: str
    description: str
    target_domain: str
    status: AdaptationStatus
    prediction_validity: PredictionValidity
    fault_localization_validity: str = "NOT_VALIDATED"
    features: List[str]
    training_sample_count: int
    validation_metrics: Optional[Dict[str, Any]] = None
    calibrated_thresholds: Optional[Dict[str, float]] = None
    formula: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class ModelComparisonRow(BaseModel):
    strategy_code: str
    model_name: str
    status: AdaptationStatus
    formula: Optional[str] = None
    mae_degC: Optional[float]
    rmse_degC: Optional[float]
    mean_bias_degC: Optional[float]
    r2_score: Optional[float]
    false_alarm_rate_pct: Optional[float]
    event_recall_pct: Optional[float]
    chw_valve_recall_pct: Optional[float]

class AdaptationSummaryResponse(BaseModel):
    target_domain: str
    scenario_id: str
    dataset_sha256: str
    split_info: Dict[str, Any]
    models_comparison: List[ModelComparisonRow]
    best_adapted_model_id: str
    mae_reduction_pct: float
    limitations: List[str]
    provenance_note: str

class PredictionPoint(BaseModel):
    datetime: str
    actual_sa_temp: Optional[float]
    source_pred_sa_temp: Optional[float]
    adapted_pred_sa_temp: Optional[float]
    source_residual: Optional[float]
    adapted_residual: Optional[float]
    is_fault: bool
    fault_label: Optional[str] = None

class AdaptationPredictionsResponse(BaseModel):
    target_domain: str
    model_id: str
    status: AdaptationStatus
    total_points: int
    downsampled_points: int
    points: List[PredictionPoint]
