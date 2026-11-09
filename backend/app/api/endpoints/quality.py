from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.data_quality import DataQualityReport
from backend.app.services.quality_service import QualityService

router = APIRouter()

@router.get("/data-quality", response_model=DataQualityReport)
def get_data_quality(
    scenario_id: str = Query(..., description="ID сценария"),
    db: Session = Depends(get_db)
):
    return QualityService.evaluate_quality(db=db, scenario_id=scenario_id)
