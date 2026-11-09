import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Scenario, DiagnosticEvent
from backend.app.schemas.ml import (
    ModelListItem,
    MLPredictionResponse,
    MLPredictionPoint,
    DetectRequest
)
from backend.app.schemas.diagnostics import DiagnosticEventRead
from ml.virtual_sensor.inference import VirtualSensorInferenceEngine

router = APIRouter(prefix="/ml")
inference_engine = VirtualSensorInferenceEngine()

@router.get("/models", response_model=List[ModelListItem])
def list_models():
    """Returns list of available trained ML models."""
    raw_models = inference_engine.list_available_models()
    result = []
    for m in raw_models:
        m_id = m.get("model_id", "")
        is_adap = (
            m_id.startswith("csiro-")
            or m.get("source_kind") == "REAL_FIELD_BMS"
            or m.get("target_domain") == "CSIRO_AHU9"
            or m.get("model_type") in ["adaptation_calibrator", "ridge_direct", "lgbm_direct", "residual_ridge"]
        )
        thresh = m.get("thresholds") or m.get("calibrated_thresholds") or {}
        result.append(ModelListItem(
            model_id=m_id,
            name=m.get("name", m_id),
            description=m.get("description", ""),
            model_type=m.get("model_type", "adaptation_calibrator" if is_adap else "lightgbm"),
            target=m.get("target", "SA_TEMP"),
            target_unit=m.get("target_unit", "degC"),
            features=m.get("features", []),
            train_scenario_id=m.get("train_scenario_id", ""),
            validation_metrics=m.get("validation_metrics", {}),
            thresholds=thresh,
            created_at=m.get("created_at", ""),
            target_domain=m.get("target_domain", "CSIRO_AHU9" if is_adap else "LBNL_SDAHU"),
            source_kind=m.get("source_kind", "REAL_FIELD_BMS" if is_adap else "SIMULATED_BENCHMARK"),
            is_adaptation=is_adap
        ))
    return result

@router.get("/models/{model_id}")
def get_model_metadata(model_id: str):
    """Returns full metadata and training config for a given model."""
    try:
        _, _, meta = inference_engine.load_model(model_id)
        return meta.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found. Status: MODEL_NOT_TRAINED")

@router.get("/predictions", response_model=MLPredictionResponse)
def get_predictions(
    scenario_id: str = Query(..., description="ID of the scenario to predict"),
    model_id: str = Query("vs-sa-temp-v1", description="ID of the virtual sensor model"),
    threshold_policy: str = Query("three_sigma", description="Policy: three_sigma, q95, q99, mad"),
    max_points: Optional[int] = Query(1500, description="Max points for frontend chart rendering")
):
    """Returns synchronized time-series of actual, predicted, and residual values."""
    try:
        res = inference_engine.predict_scenario(
            scenario_id=scenario_id,
            model_id=model_id,
            threshold_policy=threshold_policy,
            max_points=max_points
        )
        return MLPredictionResponse(
            scenario_id=res.scenario_id,
            model_id=res.model_id,
            target=res.target,
            unit=res.unit,
            total_points=res.total_points,
            operating_points=res.operating_points,
            alarm_points=res.alarm_points,
            alarm_episodes_count=res.alarm_episodes_count,
            threshold_policy=res.threshold_policy,
            threshold_value=res.threshold_value,
            metrics=res.metrics,
            points=[
                MLPredictionPoint(
                    timestamp=p.timestamp,
                    actual=p.actual,
                    predicted=p.predicted,
                    residual_signed=p.residual_signed,
                    residual_abs=p.residual_abs,
                    threshold=p.threshold,
                    is_operating=p.is_operating,
                    is_alarm=p.is_alarm,
                    status=p.status
                )
                for p in res.points
            ]
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        status_code = 400 if "INCOMPATIBLE_DATASET_DOMAIN" in str(e) else 422
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@router.post("/detect", response_model=List[DiagnosticEventRead])
def run_ml_detection(req: DetectRequest, db: Session = Depends(get_db)):
    """Runs virtual sensor anomaly detection and records diagnostic events in database."""
    scenario = db.query(Scenario).filter(Scenario.id == req.scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{req.scenario_id}' not found")

    try:
        res = inference_engine.predict_scenario(
            scenario_id=req.scenario_id,
            model_id=req.model_id,
            threshold_policy=req.threshold_policy,
            max_points=None  # Full non-downsampled series for exact event detection
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        status_code = 400 if "INCOMPATIBLE_DATASET_DOMAIN" in str(e) else 422
        raise HTTPException(status_code=status_code, detail=str(e))

    # Remove previous ML events for this scenario & model
    db.query(DiagnosticEvent).filter(
        DiagnosticEvent.scenario_id == req.scenario_id,
        DiagnosticEvent.conclusion_type == "VIRTUAL_SENSOR_RESIDUAL"
    ).delete()

    events_to_create = []
    in_alarm = False
    ep_start = ""
    ep_points = 0
    max_res = 0.0

    for pt in res.points:
        if pt.is_alarm:
            if not in_alarm:
                in_alarm = True
                ep_start = pt.timestamp
                ep_points = 1
                max_res = pt.residual_abs or 0.0
            else:
                ep_points += 1
                if pt.residual_abs and pt.residual_abs > max_res:
                    max_res = pt.residual_abs
        else:
            if in_alarm:
                # Close episode
                events_to_create.append(DiagnosticEvent(
                    id=f"ev_ml_{uuid.uuid4().hex[:12]}",
                    scenario_id=req.scenario_id,
                    started_at=ep_start,
                    ended_at=pt.timestamp,
                    rule_id="VIRTUAL_SENSOR_RESIDUAL_ALERT",
                    severity="WARNING" if max_res < 4.0 else "CRITICAL",
                    conclusion_type="VIRTUAL_SENSOR_RESIDUAL",
                    generated_by_version=req.model_id,
                    evidence_json={
                        "model_id": req.model_id,
                        "target": res.target,
                        "unit": res.unit,
                        "threshold_policy": req.threshold_policy,
                        "threshold_value": res.threshold_value,
                        "max_residual_abs": round(max_res, 3),
                        "duration_minutes": ep_points,
                        "scientific_disclaimer": "Выявлено отклонение модели виртуального датчика. Остаток является индикатором несоответствия теплового баланса (detector), а не однозначным доказательством отказа конкретного датчика."
                    }
                ))
                in_alarm = False

    if in_alarm and len(res.points) > 0:
        events_to_create.append(DiagnosticEvent(
            id=f"ev_ml_{uuid.uuid4().hex[:12]}",
            scenario_id=req.scenario_id,
            started_at=ep_start,
            ended_at=res.points[-1].timestamp,
            rule_id="VIRTUAL_SENSOR_RESIDUAL_ALERT",
            severity="WARNING" if max_res < 4.0 else "CRITICAL",
            conclusion_type="VIRTUAL_SENSOR_RESIDUAL",
            generated_by_version=req.model_id,
            evidence_json={
                "model_id": req.model_id,
                "target": res.target,
                "unit": res.unit,
                "threshold_policy": req.threshold_policy,
                "threshold_value": res.threshold_value,
                "max_residual_abs": round(max_res, 3),
                "duration_minutes": ep_points,
                "scientific_disclaimer": "Выявлено отклонение модели виртуального датчика. Остаток является индикатором несоответствия теплового баланса (detector), а не однозначным доказательством отказа конкретного датчика."
            }
        ))

    for ev in events_to_create:
        db.add(ev)
    db.commit()

    return events_to_create

@router.get("/events", response_model=List[DiagnosticEventRead])
def get_ml_events(scenario_id: str, db: Session = Depends(get_db)):
    """Returns detected ML virtual sensor events for a scenario."""
    events = db.query(DiagnosticEvent).filter(
        DiagnosticEvent.scenario_id == scenario_id,
        DiagnosticEvent.conclusion_type == "VIRTUAL_SENSOR_RESIDUAL"
    ).all()
    return events
