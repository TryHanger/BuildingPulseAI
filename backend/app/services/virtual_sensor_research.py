"""Read-only inference from an explicitly pinned local research registry."""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.services.g2_mode import evaluate_modes
from backend.app.services.sat_daily_coverage import POLICY_VERSION, Status, assess

Scope = Literal["SIMULATED_BENCHMARK"]
SA = "SA_TEMP"
PREDICTION_LOCK = Lock()
CONTEXT = ("hour", "month", "day_of_week")
TARGETS = frozenset({SA, "MA_TEMP", "RA_TEMP", *(f"ZONE_TEMP_{i}" for i in range(1, 6))})
SOURCE_SHA = "8295fcf0f55bc955937cb4ec0198512c28e5ede32e6bbf735257b0df55426471"
PROTOCOL_SHA = "50e4fbf3e84cdbed3edd2eccd9fecdb49ce2eaeb219206d02fd624d1b18a966c"
TTL_SHA = "7dbd8403cc85d49c047173f910aae8a85a297d02f9b7ddb779de7a1887d3aa93"
BASIC_CHANNELS = frozenset({
    "CHWC_VLV_DM", "MA_TEMP", "OA_DMPR_DM", "OA_TEMP", "RA_DMPR_DM", "RA_TEMP",
    "RF_CS", "RF_SPD_DM", SA, "SA_TEMPSPT", "SF_CS", "SF_SPD_DM", *(f"ZONE_TEMP_{i}" for i in range(1, 6)),
})


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def schema_digest(schema: dict) -> str:
    return digest(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode())


class ArtifactError(ValueError):
    pass


class Case(BaseModel):
    id: str
    label: str
    member: str
    member_sha256: str
    alias_status: Literal["PUBLISHER_BASELINE", "UNVERIFIED_PUBLISHER_ALIAS"]
    days: list[str]


class ResearchMethod(BaseModel):
    id: Literal["SAT_ONLY", "SYSTEM_MAX_8", "SAT_MINUS_SETPOINT"]
    version: str
    availability: Literal["ARCHIVE_DAY_API", "FULL_COHORT_RESEARCH_REPORT"]


class BaselineComparison(BaseModel):
    evidence: Literal["REPRO_01_SAVED_DAILY_CSV"] = "REPRO_01_SAVED_DAILY_CSV"
    detector: Literal["SYSTEM_MAX_8"] = "SYSTEM_MAX_8"
    arm: Literal["PRODUCT_BASIC", "PRODUCT_BASIC_WITHOUT_COMMANDS"]
    comparator: str
    paired_days: int
    lgbm_tp: int
    comparator_tp: int
    lgbm_fp: int
    comparator_fp: int
    both_tp: int


class EvidenceBoundary(BaseModel):
    cohort: Literal["PREVIOUSLY_INSPECTED_SIMULATION"] = "PREVIOUSLY_INSPECTED_SIMULATION"
    external_validation: Literal["BLOCKED_EXTERNAL_VALIDATION"] = "BLOCKED_EXTERNAL_VALIDATION"
    alarm_meaning: Literal["MODEL_RESIDUAL_ONLY"] = "MODEL_RESIDUAL_ONLY"


class Metadata(BaseModel):
    scope: Scope = "SIMULATED_BENCHMARK"
    use: Literal["RESEARCH_ONLY"] = "RESEARCH_ONLY"
    arm: Literal["PRODUCT_BASIC"] = "PRODUCT_BASIC"
    source_sha256: str
    ttl_sha256: str
    schema_sha256: str
    protocol_sha256: str
    integration_protocol_sha256: str
    source_timezone: str
    timestamp_format: str
    model_id: str
    mode: str
    split: dict[str, str]
    versions: dict[str, str]
    feature_order: list[str]
    available_channels: list[str]
    feature_roles: dict[str, str]
    cases: list[Case]
    policy_version: Literal[POLICY_VERSION] = POLICY_VERSION
    evidence_boundary: EvidenceBoundary
    methods: list[ResearchMethod]
    comparisons: list[BaselineComparison]


class Point(BaseModel):
    timestamp: str
    actual: float
    predicted: float
    absolute_residual: float
    z: float


class Day(BaseModel):
    status: Status
    reason: str | None = None
    case: Case
    day: str
    metadata: Metadata
    evaluated_minutes: int
    calendar_minutes: Literal[1440] = 1440
    running_minutes: int | None = None
    continuous_minutes: int = 0
    method: Literal["SAT_ONLY"] = "SAT_ONLY"
    coverage: float = Field(ge=0, le=1)
    daily_score: float | None = None
    threshold: Literal[3] = 3
    alert: Literal["MODEL_ANOMALY"] | None = None
    points: list[Point]
    present_channels: list[str]


def checked_payload(root: Path, entry: dict) -> bytes:
    file = (root / entry["file"]).resolve(strict=True)
    if file.parent != root or file.name != entry["file"]:
        raise ArtifactError("Invalid local artifact path")
    data = file.read_bytes()
    if digest(data) != entry["sha256"]:
        raise ArtifactError("Artifact SHA mismatch")
    return data


def registry(root: Path, manifest_sha: str):
    """Only an operator-configured manifest hash can authorize native models and windows."""
    root = root.resolve(strict=True)
    raw = checked_payload(root, {"file": "MODEL_ARTIFACT_MANIFEST.json", "sha256": manifest_sha})
    manifest = json.loads(raw)
    schema = manifest["schema"]
    model_entries = manifest["models"]
    if (manifest["scope"] != "SIMULATED_BENCHMARK" or manifest["use"] != "RESEARCH_ONLY"
            or manifest["arm"] != "PRODUCT_BASIC" or manifest["source_sha256"] != SOURCE_SHA
            or manifest["ttl_sha256"] != TTL_SHA or manifest["protocol_sha256"] != PROTOCOL_SHA
            or manifest["schema_sha256"] != schema_digest(schema)
            or set(schema["feature_orders"]) != TARGETS or set(model_entries) != TARGETS
            or set(schema["available_channels"]) != BASIC_CHANNELS):
        raise ArtifactError("Registry scope, source or schema mismatch")
    for target, entry in model_entries.items():
        order = schema["feature_orders"][target]
        if (order != entry["feature_order"] or len(set(order)) != len(order) or target in order
                or tuple(order[-3:]) != CONTEXT or len(order) < 6
                or not set(order[:-3]) <= BASIC_CHANNELS or entry["target"] != target
                or entry["scaler"] != "NONE_NATIVE_LIGHTGBM" or entry["format"] != "LIGHTGBM_NATIVE_TEXT"
                or not math.isfinite(entry["abs_center"]) or entry["abs_center"] < 0
                or (entry["abs_scale"] is not None and
                    (not math.isfinite(entry["abs_scale"]) or entry["abs_scale"] <= 1e-12))):
            raise ArtifactError("Model feature or normalization mismatch")
        # Validate all members without loading model objects or telemetry into the process.
        checked_payload(root, entry)
    for case_id, entry in manifest["windows"].items():
        if case_id != entry["id"] or entry["source_sha256"] != SOURCE_SHA:
            raise ArtifactError("Window source mismatch")
        checked_payload(root, entry)
    meta = Metadata(
        **{key: manifest[key] for key in (
            "source_sha256", "ttl_sha256", "schema_sha256", "protocol_sha256",
            "integration_protocol_sha256", "source_timezone", "timestamp_format", "mode", "split", "versions")},
        model_id=model_entries[SA]["model_id"], feature_order=schema["feature_orders"][SA],
        available_channels=schema["available_channels"], feature_roles=schema["feature_roles"],
        cases=[Case.model_validate(entry) for entry in manifest["windows"].values()],
        methods=[
            ResearchMethod(id="SAT_ONLY", version=model_entries[SA]["model_id"], availability="ARCHIVE_DAY_API"),
            ResearchMethod(id="SYSTEM_MAX_8", version=f"repro02-registry-{manifest_sha[:12]}",
                           availability="FULL_COHORT_RESEARCH_REPORT"),
            ResearchMethod(id="SAT_MINUS_SETPOINT", version="repro01-sat-setpoint-v1",
                           availability="FULL_COHORT_RESEARCH_REPORT"),
        ],
        comparisons=manifest["comparisons"],
        evidence_boundary=EvidenceBoundary(),
    )
    return root, manifest, meta


@lru_cache(maxsize=8)
def native_model(payload: bytes, feature_order: tuple[str, ...], version: str):
    import lightgbm
    from lightgbm import Booster

    if lightgbm.__version__ != version:
        raise ArtifactError("LightGBM version mismatch")
    model = Booster(model_str=payload.decode())
    if tuple(model.feature_name()) != feature_order:
        raise ArtifactError("Native feature order mismatch")
    return model


def sat_model(root: Path, manifest_sha: str):
    folder, manifest, meta = registry(root, manifest_sha)
    return native_model(checked_payload(folder, manifest["models"][SA]), tuple(meta.feature_order),
                        meta.versions["lightgbm"])


def infer(root: Path, manifest_sha: str, case_id: str, day: str) -> Day:
    import numpy as np
    import pandas as pd

    folder, manifest, meta = registry(root, manifest_sha)
    case = next(case for case in meta.cases if case.id == case_id)
    entry = manifest["windows"][case_id]
    model_entry = manifest["models"][SA]
    frame = pd.read_parquet(BytesIO(checked_payload(folder, entry)))
    if "timestamp" not in frame or "eligible" not in frame:
        raise ArtifactError("Missing time or mode eligibility receipt")
    index = pd.DatetimeIndex(frame.pop("timestamp"))
    if (index.tz is not None or not index.is_monotonic_increasing or index.has_duplicates
            or index.normalize().strftime("%Y-%m-%d").unique().tolist() != case.days
            or not len(index) or index.size != 1440 * len(case.days) or not (np.diff(index.as_unit("ns").asi8) == 60_000_000_000).all()
            or not (index == index.floor("min")).all() or index[0] != index[0].normalize()
            or frame["eligible"].dtype != bool):
        raise ArtifactError("Window clock or eligibility mismatch")
    frame.index = index
    required = {*meta.available_channels}
    missing = sorted(required - set(frame.columns))
    base = {"case": case, "day": day, "metadata": meta, "evaluated_minutes": 0, "coverage": 0, "points": [],
            "present_channels": sorted(required & set(frame.columns))}
    if missing:
        return Day(**base, status="NOT_EVALUABLE", reason="MISSING_BASIC_CHANNELS: " + ", ".join(missing))
    if model_entry["abs_scale"] is None:
        return Day(**base, status="NOT_EVALUABLE", reason="CONSTANT_CALIBRATION_SCALE")
    midnight = pd.Timestamp(day)
    window = (index >= midnight) & (index < midnight + pd.Timedelta(days=1))
    fan = frame.loc[(index >= midnight - pd.Timedelta(minutes=5)) & (index <= index[window][-1]), "SF_SPD_DM"]
    if not fan.isin([0, 1]).all():
        return Day(**base, status="NOT_EVALUABLE", reason="UNKNOWN_FAN_TIMELINE")
    # The signed eligibility receipt supplies carry-in for an archive starting mid-run.
    modes = evaluate_modes((tick, {"SF_SPD_DM": value}) for tick, value in fan.items())
    running = pd.Series([mode.fan_state == "RUNNING" for mode in modes], index=fan.index).loc[index[window]]
    eligible = frame.loc[window, "eligible"]
    carry_in = (running.index < index[0] + pd.Timedelta(minutes=5)) & fan.loc[running.index].eq(1)
    running |= eligible & carry_in
    if (eligible & ~running).any():
        raise ArtifactError("Eligibility outside the RUNNING timeline")
    running_count = int(running.sum())
    finite = np.isfinite(frame.loc[window, meta.available_channels]).all(axis=1)
    selected = frame.loc[finite.index[finite & eligible]].copy()
    coverage = assess(selected.index.hour * 60 + selected.index.minute, running_count)
    if selected.empty:
        reason = "NONFINITE_BASIC_INPUTS" if eligible.any() else coverage.reason
        return Day(**base, status=coverage.status, reason=reason, running_minutes=running_count)
    selected["hour"], selected["month"], selected["day_of_week"] = (
        selected.index.hour, selected.index.month, selected.index.dayofweek)
    model = native_model(checked_payload(folder, model_entry), tuple(meta.feature_order), meta.versions["lightgbm"])
    with PREDICTION_LOCK:
        predicted = model.predict(selected[meta.feature_order], validate_features=True, num_threads=1)
    actual = selected[SA].to_numpy()
    absolute = np.abs(actual - predicted)
    z = (absolute - model_entry["abs_center"]) / model_entry["abs_scale"]
    if not np.isfinite(z).all():
        raise ArtifactError("Nonfinite score")
    points = [Point(timestamp=str(ts), actual=a, predicted=p, absolute_residual=r, z=value)
              for ts, a, p, r, value in zip(selected.index, actual, predicted, absolute, z, strict=True)]
    score = float(z.mean()) if coverage.status == "EVALUATED" else None
    return Day(case=case, day=day, metadata=meta, status=coverage.status, reason=coverage.reason,
               evaluated_minutes=len(points), running_minutes=running_count,
               continuous_minutes=coverage.continuous_minutes, coverage=len(points) / 1440, daily_score=score,
               alert="MODEL_ANOMALY" if score is not None and score > 3 else None,
               points=points, present_channels=sorted(required))
