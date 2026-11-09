"""Isolated GET-only endpoints; no FDD events, database sessions or uploaded artifacts."""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.core.config import settings
from backend.app.services.virtual_sensor_research import Day, Metadata, infer, registry

router = APIRouter(prefix="/research/virtual-sensors", tags=["Research virtual sensors"])
logger = logging.getLogger(__name__)
UNAVAILABLE = {503: {"description": "Trusted research registry disabled or unavailable"}}


def configured():
    root = settings.VIRTUAL_SENSOR_RESEARCH_DIR
    manifest_sha = settings.VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256
    if not root or not manifest_sha:
        raise HTTPException(status_code=503, detail="RESEARCH_REGISTRY_NOT_CONFIGURED")
    return root, manifest_sha


def unavailable(error):
    logger.warning("Virtual sensor research registry unavailable (%s)", type(error).__name__)
    return HTTPException(status_code=503, detail="RESEARCH_ARTIFACT_UNAVAILABLE")


@router.get("", response_model=Metadata, responses=UNAVAILABLE)
def metadata():
    root, signature = configured()
    try:
        return registry(root, signature)[2]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise unavailable(error) from error


@router.get("/day", response_model=Day, responses={**UNAVAILABLE, 404: {"description": "Day outside archived research window"}})
def research_day(request: Request, case: Literal["healthy", "sa-plus-2"], day: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$")):
    """Select one case and one source-local day from the pinned SAT archive."""
    if len(request.query_params.multi_items()) != 2:
        raise HTTPException(status_code=422, detail="ARCHIVE_CASE_AND_DAY_ONLY")
    root, signature = configured()
    try:
        _, _, meta = registry(root, signature)
        window = next((entry for entry in meta.cases if entry.id == case), None)
        if window is None or day not in window.days:
            raise HTTPException(status_code=404, detail="RESEARCH_WINDOW_NOT_FOUND")
        return infer(root, signature, case, day)
    except (OSError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as error:
        raise unavailable(error) from error
