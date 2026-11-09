from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class ThresholdConfig(BaseModel):
    q95: float = Field(default=1.83, description="95th percentile of absolute residual on validation set")
    q99: float = Field(default=3.0, description="99th percentile of absolute residual on validation set")
    three_sigma: float = Field(default=3.01, description="Mean + 3*std of absolute residual on validation set")
    mad: float = Field(default=0.2, description="Median + 3*1.4826*MAD on validation set")

class PersistenceFilterConfig(BaseModel):
    k: int = Field(default=10, description="Minimum anomalous points required to trigger alarm")
    n: int = Field(default=15, description="Rolling window size in minutes")

class ModelMetadata(BaseModel):
    model_id: str
    name: str
    description: str
    model_type: str
    target: str = "SA_TEMP"
    target_unit: str = "degC"
    features: List[str] = Field(default_factory=list)
    feature_units: Dict[str, str] = Field(default_factory=dict)
    operational_gating_feature: Optional[str] = "SF_SPD_DM"
    train_scenario_id: Optional[str] = ""
    train_range: Optional[str] = ""
    val_range: Optional[str] = ""
    test_range: Optional[str] = ""
    split_hash: Optional[str] = ""
    random_state: int = 42
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    validation_metrics: Dict[str, Any] = Field(default_factory=dict)
    thresholds: Optional[ThresholdConfig] = None
    calibrated_thresholds: Optional[Dict[str, float]] = None
    persistence_filter: Optional[PersistenceFilterConfig] = Field(default_factory=lambda: PersistenceFilterConfig())
    library_versions: Dict[str, str] = Field(default_factory=dict)
    created_at: Optional[str] = ""
    target_domain: Optional[str] = None
    source_kind: Optional[str] = None
    strategy_code: Optional[str] = None
    status: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class PredictionPoint(BaseModel):
    timestamp: str
    actual: Optional[float] = None
    predicted: Optional[float] = None
    residual_signed: Optional[float] = None
    residual_abs: Optional[float] = None
    threshold: Optional[float] = None
    is_operating: bool = True
    is_alarm: bool = False
    status: str = "OK"

class ScenarioPredictionResult(BaseModel):
    scenario_id: str
    model_id: str
    target: str = "SA_TEMP"
    unit: str = "degC"
    total_points: int
    operating_points: int
    alarm_points: int
    alarm_episodes_count: int
    threshold_policy: str
    threshold_value: float
    points: List[PredictionPoint]
    metrics: Optional[Dict[str, float]] = None
