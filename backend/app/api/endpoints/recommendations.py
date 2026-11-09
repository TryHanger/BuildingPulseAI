import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Scenario, Dataset
from backend.app.schemas.recommendations import (
    RecommendableChannelItem,
    SensorRecommendationRequest,
    SensorRecommendationResponse
)
from ml.diagnostics.recommender import SensorRecommendationService

router = APIRouter()

@router.get("/diagnostics/recommendable-channels", response_model=List[RecommendableChannelItem])
def get_recommendable_channels(
    profile_id: str = Query("BASIC", description="Идентификатор текущего профиля")
):
    """
    Returns candidate actuator feedback channels for recommendation and their status.
    """
    items = SensorRecommendationService.get_recommendable_channels(profile_id=profile_id)
    return [RecommendableChannelItem(**item) for item in items]

@router.post("/sensors/recommend", response_model=SensorRecommendationResponse)
def get_sensor_recommendation(
    request: SensorRecommendationRequest,
    db: Session = Depends(get_db)
):
    """
    Computes validation-grounded sensor recommendation for the given scenario and profile.
    Enforces Domain Guard and strict anti-leakage invariants.
    """
    domain_status = "VALIDATED"
    if request.scenario_id:
        scenario = db.query(Scenario).filter(Scenario.id == request.scenario_id).first()
        if scenario:
            dataset = db.query(Dataset).filter(Dataset.id == scenario.dataset_id).first()
            source_kind = dataset.source_kind if dataset else "UNKNOWN"
            if source_kind != "SIMULATED_BENCHMARK" and not request.allow_unvalidated:
                domain_status = "OUT_OF_DOMAIN"

    rec_result = SensorRecommendationService.recommend(
        scenario_id=request.scenario_id,
        profile_id=request.profile_id,
        domain_status=domain_status,
        coverage_target=request.coverage_target,
        policy_id=request.policy_id
    )

    return SensorRecommendationResponse(**rec_result.to_dict())

@router.get("/experiments/stage5/recommendation-summary")
def get_stage5_recommendation_summary():
    """
    Returns persisted H3 experiment summary comparing Random, Fixed, and Validation-Based strategies.
    """
    run_file = Path("research/runs/stage5_recommendation_eval.json")
    if not run_file.exists():
        return {
            "status": "NOT_EVALUATED",
            "message": "Манифест эксперимента stage5_recommendation_eval.json пока не сгенерирован"
        }
    with open(run_file, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/experiments/stage5/external-summary")
def get_stage5_external_summary():
    """
    Returns persisted external building validation summary (CSIRO / RBC compatibility and telemetry).
    """
    run_file = Path("research/runs/stage5_external_validation.json")
    if not run_file.exists():
        return {
            "status": "PENDING_EXECUTION",
            "message": "Манифест внешнего здания stage5_external_validation.json пока не сгенерирован"
        }
    with open(run_file, "r", encoding="utf-8") as f:
        return json.load(f)
