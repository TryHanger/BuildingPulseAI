from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RecommendableChannelItem(BaseModel):
    channel: str
    display_name: str
    component: str
    already_present: bool
    is_recommendable: bool
    reason: str

class CandidateScoreRead(BaseModel):
    channel: str
    channel_name_ru: str
    component: str
    delta_selective_risk_validation: Optional[float] = None
    coverage_target: float = 0.60
    coverage_actual: Optional[float] = None
    eligible_groups: Optional[int] = None
    decision: str
    reason: str

class SensorRecommendationRequest(BaseModel):
    scenario_id: Optional[str] = Field(None, description="ID сценария телеметрии")
    profile_id: str = Field("BASIC", description="Активный профиль наблюдаемости")
    coverage_target: float = Field(0.60, description="Целевой уровень селективного охвата (Coverage c)")
    policy_id: str = Field("validation_risk_optimal", description="Политика выбора")
    allow_unvalidated: bool = Field(False, description="Разрешить рекомендацию для непроверенных доменов")

class SensorRecommendationResponse(BaseModel):
    scenario_id: Optional[str] = None
    profile_id: str
    status: str
    recommended_channel: Optional[str] = None
    recommended_channel_name_ru: Optional[str] = None
    reason: str
    candidate_scores: List[CandidateScoreRead]
    evidence_source: str
    training_domain: str
    model_version: str
    policy_version: str
    limitations: List[str]
