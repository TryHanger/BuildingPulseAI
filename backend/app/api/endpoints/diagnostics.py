import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.diagnostics import (
    DiagnosticEventRead,
    RuleRunRequest,
    RuleRunResponse,
    ScenarioDiagnosticSummary,
    SensorProfileItem
)
from backend.app.services.diagnostics_service import DiagnosticsService

router = APIRouter()

@router.get("/diagnostics/profiles", response_model=List[SensorProfileItem])
def get_sensor_profiles():
    """
    Returns the list of 5 executable sensor observability profiles:
    BASIC, BASIC_PLUS_VALVE, BASIC_PLUS_DAMPER, BASIC_PLUS_BOTH, FULL.
    """
    return DiagnosticsService.list_sensor_profiles()

@router.get("/diagnostics/summary", response_model=ScenarioDiagnosticSummary)
def get_diagnostic_summary(
    scenario_id: str = Query(..., description="ID сценария"),
    model_id: str = Query("vs-sa-temp-v2", description="ID виртуального датчика"),
    threshold_policy: str = Query("three_sigma", description="Политика порога: three_sigma, q95, mad, q99"),
    profile_id: str = Query("BASIC", description="Профиль наблюдаемости: BASIC, BASIC_PLUS_VALVE, etc."),
    allow_unvalidated: bool = Query(False, description="Разрешить исследовательский режим для непроверенных источников"),
    db: Session = Depends(get_db)
):
    """
    Returns high-level scenario diagnostic summary from Formal Decision Layer:
    detection status, single cause, multiple plausible candidates, physical evidence,
    missing channels for the profile, and domain status.
    """
    return DiagnosticsService.get_scenario_diagnostic_summary(
        db=db,
        scenario_id=scenario_id,
        model_id=model_id,
        threshold_policy=threshold_policy,
        profile_id=profile_id,
        allow_unvalidated=allow_unvalidated
    )

@router.post("/diagnostics/run-rules", response_model=RuleRunResponse)
def run_rules(
    request: RuleRunRequest,
    db: Session = Depends(get_db)
):
    events = DiagnosticsService.run_baseline_rules(
        db=db,
        scenario_id=request.scenario_id,
        start_time=request.start_time,
        end_time=request.end_time
    )
    return RuleRunResponse(
        scenario_id=request.scenario_id,
        algorithm_type="RULE_BASELINE",
        events_found=len(events),
        events=events
    )

@router.get("/diagnostics/events", response_model=List[DiagnosticEventRead])
def get_events(
    scenario_id: str = Query(..., description="ID сценария"),
    conclusion_type: Optional[str] = Query(None, description="Тип заключения (PHYSICAL_BASELINE, VIRTUAL_SENSOR_RESIDUAL)"),
    db: Session = Depends(get_db)
):
    return DiagnosticsService.get_events(
        db=db,
        scenario_id=scenario_id,
        conclusion_type=conclusion_type
    )

@router.get("/experiments/stage4/summary")
def get_stage4_experiments_summary():
    """
    Returns persisted Stage 4 scientific experiment summaries (E4.1 Risk-Coverage and E4.2 Profiles).
    """
    runs_dir = Path("research/runs")
    decision_run_file = runs_dir / "stage4_decision_layer_eval.json"
    obs_run_file = runs_dir / "stage4_observability_eval.json"

    res: Dict[str, Any] = {}
    if decision_run_file.exists():
        with open(decision_run_file, "r", encoding="utf-8") as f:
            res["decision_layer_eval"] = json.load(f)
    if obs_run_file.exists():
        with open(obs_run_file, "r", encoding="utf-8") as f:
            res["observability_eval"] = json.load(f)

    return res
