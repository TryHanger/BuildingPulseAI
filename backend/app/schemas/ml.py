from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class ModelListItem(BaseModel):
    model_id: str
    name: str
    description: str
    model_type: str
    target: str = "SA_TEMP"
    target_unit: str = "degC"
    features: List[str]
    train_scenario_id: Optional[str] = ""
    validation_metrics: Dict[str, Any]
    thresholds: Dict[str, float]
    created_at: str
    target_domain: Optional[str] = None
    source_kind: Optional[str] = None
    is_adaptation: bool = False

class DetectRequest(BaseModel):
    scenario_id: str
    model_id: str = "vs-sa-temp-v1"
    threshold_policy: str = Field(default="three_sigma", description="Policy: three_sigma, q95, q99, mad")

class MLPredictionPoint(BaseModel):
    timestamp: str
    actual: Optional[float] = None
    predicted: Optional[float] = None
    residual_signed: Optional[float] = None
    residual_abs: Optional[float] = None
    threshold: Optional[float] = None
    is_operating: bool = True
    is_alarm: bool = False
    status: str = "OK"

class MLPredictionResponse(BaseModel):
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
    metrics: Optional[Dict[str, float]] = None
    points: List[MLPredictionPoint]
