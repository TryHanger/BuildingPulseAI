"""Serve only the reviewed Stage09 observations and archived outcomes."""
from hashlib import sha256
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/research/field-evidence", tags=["Research field evidence"])
BUNDLE = Path(__file__).resolve().parents[2] / "research_data" / "field_evidence_10.json"
BUNDLE_SHA256 = "cfd6df405d4e99324457a9cfa744e6c5bd4d994b21b9a87f10dd5f43f45726b9"

Bit = Literal[0, 1] | None
AHU = Literal["AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24"]


class Observation(BaseModel):
    partition: Literal["PRE", "WINDOW"]
    native_time: str
    relative_seconds: int
    supply: Bit
    exhaust: Bit
    heat_request: Bit
    cool_request: Bit
    supply_evidence: str
    paired_evidence: str
    rule_version: str
    clock: str
    raw_file: str
    raw_sha256: str


class EvidenceWindow(BaseModel):
    kind: Literal["intervention", "matched_control"]
    id: str
    ahu: AHU
    start: str
    end_exclusive: str
    observations: list[Observation]
    archived_outcome: dict[str, str]
    evaluation_metadata: dict[str, str]


class SourceFile(BaseModel):
    file_id: str
    bytes: int
    publisher_sha256: str
    verified_sha256: str


class Provenance(BaseModel):
    dataset_doi: str
    version: Literal[1]
    license: str
    dataset_url: str
    article_doi: str
    site_count: Literal[1]
    intervention_event_day_count: Literal[1]
    rule_version: Literal["bas-fan-observation@1.0.0"]
    protocol_sha256: str
    stage09_zip_sha256: str
    source_manifest_sha256: str
    cadence_seconds: Literal[300]
    clock: Literal["UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S"]
    timestamp_column: Literal["Time"]
    input_columns: dict[str, str]
    files: dict[str, SourceFile]


class FieldEvidence(BaseModel):
    provenance: Provenance
    cases: list[EvidenceWindow]


@router.get(
    "",
    response_model=FieldEvidence,
    responses={
        422: {"description": "The frozen collection accepts no query parameters"},
        503: {"description": "SOURCE_PROVENANCE_UNVERIFIED. Observations withheld."},
    },
)
def field_evidence(request: Request):
    """Return the fixed set of 12 windows, with publisher annotations kept separate."""
    if request.query_params:
        raise HTTPException(status_code=422, detail="FROZEN_COLLECTION_ONLY")

    # Verify the bytes served on every read, including after a file is removed or replaced.
    try:
        payload = BUNDLE.read_bytes()
    except OSError as error:
        raise HTTPException(status_code=503, detail="SOURCE_PROVENANCE_UNVERIFIED") from error
    if sha256(payload).hexdigest() != BUNDLE_SHA256:
        raise HTTPException(status_code=503, detail="SOURCE_PROVENANCE_UNVERIFIED")
    return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store"})
