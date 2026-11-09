from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas.telemetry import TelemetryResponse
from backend.app.services.telemetry_service import TelemetryService

router = APIRouter()

@router.get("/telemetry", response_model=TelemetryResponse)
def get_telemetry(
    scenario_id: str = Query(..., description="ID сценария"),
    channels: str = Query(..., description="Список каналов через запятую (например SA_TEMP,MA_TEMP)"),
    start: Optional[str] = Query(None, description="Начало интервала (ISO-8601)"),
    end: Optional[str] = Query(None, description="Конец интервала (ISO-8601)"),
    max_points: int = Query(settings.MAX_POINTS_DEFAULT, ge=10, le=settings.MAX_POINTS_UPPER_LIMIT),
    db: Session = Depends(get_db)
):
    channel_list = [ch.strip() for ch in channels.split(",") if ch.strip()]
    if not channel_list:
        raise HTTPException(status_code=400, detail="Параметр channels должен содержать хотя бы один канал")

    return TelemetryService.get_telemetry(
        db=db,
        scenario_id=scenario_id,
        channels=channel_list,
        start=start,
        end=end,
        max_points=max_points
    )
