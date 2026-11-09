from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Sensor
from backend.app.schemas.sensor import SensorRead, SensorListResponse

router = APIRouter()

@router.get("/sensors", response_model=SensorListResponse)
def list_sensors(
    scenario_id: str = Query(..., description="ID сценария"),
    db: Session = Depends(get_db)
):
    sensors = db.query(Sensor).filter(Sensor.scenario_id == scenario_id).all()
    return SensorListResponse(
        items=[SensorRead.model_validate(s) for s in sensors],
        total=len(sensors)
    )
