from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Scenario
from backend.app.schemas.scenario import ScenarioRead, ScenarioListResponse

router = APIRouter()

@router.get("/scenarios", response_model=ScenarioListResponse)
def list_scenarios(
    dataset_id: Optional[str] = Query(None, description="Фильтр по ID датасета"),
    db: Session = Depends(get_db)
):
    query = db.query(Scenario)
    if dataset_id:
        query = query.filter(Scenario.dataset_id == dataset_id)
    scenarios = query.all()
    return ScenarioListResponse(
        items=[ScenarioRead.model_validate(s) for s in scenarios],
        total=len(scenarios)
    )
