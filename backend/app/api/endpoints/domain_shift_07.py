"""Additive research contract for the separate reduced SAT candidate."""
from fastapi import APIRouter

from backend.app.services.domain_shift_07 import (
    ApplicabilityRequest, ApplicabilityResult, ReducedSATResearchContract, assess,
)

router = APIRouter(prefix="/research/domain-shift-07", tags=["Research applicability"])


@router.get("", response_model=ReducedSATResearchContract)
def reduced_sat_contract():
    """Return frozen candidate metadata and its negative external transfer gate."""
    return ReducedSATResearchContract()


@router.post("/applicability", response_model=ApplicabilityResult)
def reduced_sat_applicability(evidence: ApplicabilityRequest):
    """Check prospective applicability metadata without scoring or emitting incidents."""
    return assess(evidence)
