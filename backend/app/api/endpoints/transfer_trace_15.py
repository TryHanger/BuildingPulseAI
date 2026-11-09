"""Read-only view of the archived Stage06 normal-reference result."""
from hashlib import sha256
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/research/transfer-trace-15", tags=["Research transfer trace"])
BUNDLE = Path(__file__).resolve().parents[2] / "research_data" / "transfer_trace_15.json"
BUNDLE_SHA256 = "07dc60b3e1f9d479c8430ae266cdf092bd6c88aa2cffa2f9cdc4ef977643f7c3"


class TransferTraceProvenance(BaseModel):
    archive_sha256: str
    trace_sha256: str
    blocks_sha256: str
    receipt_sha256: str
    source_sha256: str
    model_sha256: str


class TransferTracePoint(BaseModel):
    model_seconds: int
    source_row: int
    sat_deg_f: float
    setpoint_deg_f: float
    prediction_deg_f: float | None
    fan_status: float
    plant_mode: int
    source_support: bool
    eligible: bool
    abstain_reason: str | None


class TransferTraceBlock(BaseModel):
    block: int
    start_model_s: int
    end_exclusive_model_s: int
    eligible_minutes: int
    z: float
    decision: Literal["ALERT", "NO_ALERT"]


class TransferTrace(BaseModel):
    provenance: TransferTraceProvenance
    clock: Literal["MODEL_SECONDS"]
    gate: Literal["STOP_OOD_HEALTHY"]
    calendar_minutes: int
    eligible_minutes: int
    independent_normal_runs: int
    threshold: Literal[3]
    blocks: list[TransferTraceBlock]
    points: list[TransferTracePoint]


@router.get(
    "",
    response_model=TransferTrace,
    responses={
        422: {"description": "The frozen trace accepts no query parameters"},
        503: {"description": "SOURCE_PROVENANCE_UNVERIFIED. Trace withheld."},
    },
)
def transfer_trace(request: Request):
    if request.query_params:
        raise HTTPException(status_code=422, detail="FROZEN_TRACE_ONLY")
    try:
        payload = BUNDLE.read_bytes()
    except OSError as error:
        raise HTTPException(status_code=503, detail="SOURCE_PROVENANCE_UNVERIFIED") from error
    if sha256(payload).hexdigest() != BUNDLE_SHA256:
        raise HTTPException(status_code=503, detail="SOURCE_PROVENANCE_UNVERIFIED")
    return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store"})
