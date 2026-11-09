from typing import List, Optional, Dict, Any
from pathlib import Path
import json
from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.adaptation import (
    TargetDatasetInfo,
    AdaptationModelCard,
    AdaptationSummaryResponse,
    AdaptationPredictionsResponse
)
from backend.app.services.adaptation_service import AdaptationService

router = APIRouter(prefix="/adaptation")

@router.get("/datasets", response_model=List[TargetDatasetInfo])
def list_adaptation_datasets():
    """Returns registered field buildings supported for domain adaptation."""
    return AdaptationService.get_supported_datasets()

@router.get("/models", response_model=List[AdaptationModelCard])
def list_adaptation_models(target: str = Query("CSIRO_AHU9", description="Target building code")):
    """Returns adaptation model candidates for target building."""
    return AdaptationService.get_adaptation_models(target=target)

@router.get("/summary", response_model=AdaptationSummaryResponse)
def get_adaptation_summary(target: str = Query("CSIRO_AHU9", description="Target building code")):
    """Returns full Pre vs Post adaptation comparison on held-out test."""
    try:
        return AdaptationService.get_adaptation_summary(target=target)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/runs/{run_id}")
def get_adaptation_run(run_id: str):
    """Returns provenance and metrics for an adaptation execution run with path traversal protection."""
    safe_name = Path(run_id).name
    if not safe_name or safe_name != run_id or "/" in run_id or "\\" in run_id:
        raise HTTPException(status_code=400, detail="Некорректный идентификатор запуска (path traversal prohibited)")

    # Support aliases for test and backward compatibility
    alias_map = {
        "stage6_train_csiro_adaptation": "stage6_csiro_adaptation_train",
        "stage6_eval_csiro_adaptation": "stage6_csiro_adaptation_eval",
    }
    actual_name = alias_map.get(safe_name, safe_name)

    runs_dir = Path("research/runs").resolve()
    target_path = (runs_dir / f"{actual_name}.json").resolve()
    try:
        if not target_path.is_relative_to(runs_dir) or not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Запуск '{run_id}' не найден")
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный путь к файлу запуска")

    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/predictions", response_model=AdaptationPredictionsResponse)
def get_adaptation_predictions(
    target: str = Query("CSIRO_AHU9", description="Target building code"),
    model_id: str = Query("csiro-ahu9-affine-v1", description="Adaptation model identifier"),
    max_points: int = Query(600, ge=50, le=2000, description="Max downsampled points for UI chart"),
    start_date: Optional[str] = Query(None, description="Start ISO datetime"),
    end_date: Optional[str] = Query(None, description="End ISO datetime")
):
    """Returns downsampled time series telemetry comparing actual, zero-shot and adapted predictions."""
    try:
        return AdaptationService.get_adaptation_predictions(
            target=target,
            model_id=model_id,
            max_points=max_points,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate predictions: {e}")
