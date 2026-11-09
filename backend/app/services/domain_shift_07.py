"""Prospective research applicability metadata. No model or telemetry access."""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictBool

SOURCE_SETPOINT = Decimal("55.184006")
FEATURE_SUPPORT = {
    "MA_TEMP": (59.861824, 109.07821),
    "OA_TEMP": (60.007996, 95.0),
    "RA_TEMP": (67.0176, 109.50728),
}


class TrainingSetpointSupport(BaseModel):
    unit: Literal["degF"] = "degF"
    span: tuple[Literal["55.184006"], Literal["55.184006"]] = ("55.184006", "55.184006")
    unique_count: Literal[1] = 1


class RecordedNormalEvidence(BaseModel):
    scope: Literal["ONE_G36_SIMULATED_NORMAL_RUN"] = "ONE_G36_SIMULATED_NORMAL_RUN"
    independent_runs: Literal[1] = 1
    evaluated_blocks: Literal[7] = 7
    lightgbm_alarm_blocks: Literal[7] = 7
    eligible_minutes: Literal[5425] = 5425
    calendar_minutes: Literal[10080] = 10080
    trace_artifact: Literal["TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"] = "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"
    stage06_archive_sha256: Literal["64ce1a8c46e163ae346df4d3bfec82d486d3a0052fc5da47a4cd2112a45e6bcf"] = (
        "64ce1a8c46e163ae346df4d3bfec82d486d3a0052fc5da47a4cd2112a45e6bcf"
    )


class ApplicabilityEvidenceLimits(BaseModel):
    self_attested_metadata_only: Literal[True] = True
    one_dimensional_feature_ranges_only: Literal[True] = True
    fan_duration_verified: Literal[False] = False


class ReducedSATResearchContract(ApplicabilityEvidenceLimits):
    candidate: Literal["reduced-thermal-sat-v1"] = "reduced-thermal-sat-v1"
    use: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    source_calibration_domain: Literal["LBNL_SIMULATED_SDAHU_2018"] = "LBNL_SIMULATED_SDAHU_2018"
    transfer_normal_gate: Literal["STOP_OOD_HEALTHY"] = "STOP_OOD_HEALTHY"
    training_setpoint_support: TrainingSetpointSupport = Field(default_factory=TrainingSetpointSupport)
    historical_normal_evidence: RecordedNormalEvidence = Field(default_factory=RecordedNormalEvidence)
    setpoint_used_as_feature: Literal[False] = False
    target_fault_eval_allowed: Literal[False] = False
    external_field_validation: Literal[False] = False
    deployment_eligible: Literal[False] = False


class ObservedFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    MA_TEMP: FiniteFloat | None = None
    OA_TEMP: FiniteFloat | None = None
    RA_TEMP: FiniteFloat | None = None


class ApplicabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_setpoint: Decimal | None = None
    setpoint_exact: StrictBool = False
    temperature_unit: str | None = None
    physical_roles_verified: StrictBool = False
    origin: Literal["VERIFIED_BAS", "UNKNOWN"] = "UNKNOWN"
    control_mode: Literal["RUNNING_WARM", "OTHER", "OFF", "UNKNOWN"] = "UNKNOWN"
    features: ObservedFeatures = Field(default_factory=ObservedFeatures)


class ApplicabilityResult(ApplicabilityEvidenceLimits):
    status: Literal["ABSTAIN_DOMAIN_SHIFT", "NOT_APPLICABLE_CONTROL_REGIME", "SOURCE_REGIME_MATCH_ONLY"]
    reason: Literal[
        "UNKNOWN_SETPOINT", "UNVERIFIED_PHYSICAL_ROLES", "UNKNOWN_OR_WRONG_TEMPERATURE_UNIT",
        "UNKNOWN_CONTROL_MODE", "OUTSIDE_CONTROL_MODE", "MISSING_REQUIRED_FEATURE",
        "OUTSIDE_SOURCE_FEATURE_SUPPORT", "SETPOINT_OUTSIDE_SOURCE_SUPPORT", "EXACT_SOURCE_SUPPORT_MATCH",
    ]
    source_setpoint_support: Literal["UNKNOWN", "OUTSIDE", "MATCH"]
    inference_authorized: Literal[False] = False
    deployment_eligible: Literal[False] = False
    incident_eligible: Literal[False] = False


def assess(observed: ApplicabilityRequest) -> ApplicabilityResult:
    if observed.origin != "VERIFIED_BAS" or not observed.physical_roles_verified:
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="UNVERIFIED_PHYSICAL_ROLES",
                                   source_setpoint_support="UNKNOWN")
    if observed.temperature_unit != "degF":
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="UNKNOWN_OR_WRONG_TEMPERATURE_UNIT",
                                   source_setpoint_support="UNKNOWN")
    if observed.active_setpoint is None or not observed.setpoint_exact:
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="UNKNOWN_SETPOINT",
                                   source_setpoint_support="UNKNOWN")

    same_setpoint = observed.active_setpoint == SOURCE_SETPOINT
    support = "MATCH" if same_setpoint else "OUTSIDE"
    if observed.control_mode == "UNKNOWN":
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="UNKNOWN_CONTROL_MODE",
                                   source_setpoint_support=support)
    if observed.control_mode != "RUNNING_WARM":
        return ApplicabilityResult(status="NOT_APPLICABLE_CONTROL_REGIME", reason="OUTSIDE_CONTROL_MODE",
                                   source_setpoint_support=support)
    values = observed.features.model_dump()
    if any(value is None for value in values.values()):
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="MISSING_REQUIRED_FEATURE",
                                   source_setpoint_support=support)
    if not same_setpoint:
        return ApplicabilityResult(status="NOT_APPLICABLE_CONTROL_REGIME", reason="SETPOINT_OUTSIDE_SOURCE_SUPPORT",
                                   source_setpoint_support="OUTSIDE")
    if any(not low <= values[name] <= high for name, (low, high) in FEATURE_SUPPORT.items()):
        return ApplicabilityResult(status="ABSTAIN_DOMAIN_SHIFT", reason="OUTSIDE_SOURCE_FEATURE_SUPPORT",
                                   source_setpoint_support="MATCH")
    return ApplicabilityResult(status="SOURCE_REGIME_MATCH_ONLY", reason="EXACT_SOURCE_SUPPORT_MATCH",
                               source_setpoint_support="MATCH")
