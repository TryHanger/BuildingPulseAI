"""Read-only Investigator over the verified LBNL source slices."""
import hashlib
import io
import json
from bisect import bisect_left
from datetime import datetime, timedelta
from functools import lru_cache
from os import fstat
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from fastapi import HTTPException

from backend.app.core.config import settings
from backend.app.services.g2_applicability import METHODS, assess
from backend.app.services.g2_mode import HOLD_SECONDS, MODE_POLICY, PHYSICAL_CONTEXT, evaluate_modes
from backend.app.services.g2_quality import SAMPLE_SECONDS, signal_quality, time_quality
from backend.app.services.g3_symptom import point_result
from backend.app.services.import_service import parse_timestamps

REGISTRY = settings.BASE_DIR / "research" / "g0-g1"
MANIFEST = json.loads((REGISTRY / "DATASET_MANIFEST.json").read_text())
SIGNAL_MAP = yaml.safe_load((REGISTRY / "SIGNAL_MAP_V1.yaml").read_text())
CLOCK_KIND = "SOURCE_SIMULATION_TIME"
SOURCES = {
    item["path"].rsplit("_lbnl_", 1)[0]: item
    for item in MANIFEST["local_slices"] if item["exact_archive_prefix"]
}
SIGNALS = {key: spec for key, spec in SIGNAL_MAP["signals"].items() if key != "SYS_CTL"}

DEMO_DIR = settings.BASE_DIR / "contracts" / "fixtures" / "g4"
DEMO_ID = "demo-g4-mat"


def demo_manifest():
    try:
        manifest = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        fail(409, "SOURCE_INTEGRITY", "The registered synthetic manifest is unreadable")
    required = {"dataset_id", "name", "sha256", "index_sha256", "first", "last", "rows"}
    if not isinstance(manifest, dict) or not required <= manifest.keys() or manifest["dataset_id"] != DEMO_ID:
        fail(409, "SOURCE_INTEGRITY", "The registered synthetic manifest is invalid")
    return manifest


def demo_dataset(source=None):
    if source is None:
        source = demo_manifest()
    return {
        "dataset_id": DEMO_ID, "name": source["name"], "source_type": "DEMO_FIXTURE",
        "equipment_id": "demo-g4-ahu", "source_member": "mixing-demo.csv", "source_url": None,
        "license_note": "Synthetic BuildingPulse fixture", "source_sha256": source["sha256"],
        "release_id": f"sha256:{source['sha256']}", "clock_kind": CLOCK_KIND, "sample_seconds": SAMPLE_SECONDS,
        "first": source["first"], "last": source["last"], "rows": source["rows"], "is_full_year": False,
        "pair_status": "PAIR_NOT_VERIFIED",
        "availability": "AVAILABLE" if (DEMO_DIR / "mixing-demo.csv").is_file() else "MISSING_SOURCE",
    }


def result_origin(source):
    return "DEMO_FIXTURE" if source.get("dataset_id") == DEMO_ID else "VERIFIED_RUNTIME"



def fail(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


def source_timestamps(values):
    try:
        timestamps = parse_timestamps(values)
    except HTTPException as exc:
        row = exc.detail.get("row")
        location = f" near CSV row {row}" if row is not None else ""
        fail(422, exc.detail["code"], f"Invalid source timestamp sequence{location}")
    if timestamps.dt.tz is not None:
        fail(409, "SOURCE_CLOCK_MISMATCH", "The registered clock has no UTC offset")
    return timestamps


def source_frame(frame):
    if "Datetime" not in frame:
        fail(422, "MISSING_TIME_COLUMN", "The registered CSV has no Datetime column")
    return frame.set_index(source_timestamps(frame.pop("Datetime")))


def start_index(index, start):
    if start is None or index.empty or start <= index[0]:
        return 0
    if start > index[-1]:
        return len(index)
    return int(index.searchsorted(start))


def source_path(source):
    raw = (settings.data_dir / "raw").resolve()
    path = (raw / source["path"]).resolve()
    if path.parent != raw:
        fail(409, "SOURCE_INTEGRITY", "Source escapes registered raw directory")
    return path


def datasets():
    items = [{
        "dataset_id": key,
        "name": Path(source["archive_member"]).name,
        "source_type": "SIMULATION",
        "equipment_id": "lbnl-sd-ahu",
        "source_member": source["archive_member"],
        "source_url": MANIFEST["archive"]["url"],
        "license_note": "CC BY 4.0 (LBNL SD-AHU)",
        "source_sha256": source["sha256"],
        "release_id": MANIFEST["release_id"],
        "clock_kind": CLOCK_KIND,
        "sample_seconds": SAMPLE_SECONDS,
        "first": source.get("first"),
        "last": source.get("last"),
        "rows": source.get("rows"),
        "is_full_year": source.get("is_full_year", False),
        "pair_status": "PAIR_NOT_VERIFIED",
        "availability": "AVAILABLE" if source_path(source).is_file() else "MISSING_SOURCE",
    } for key, source in SOURCES.items()]
    return sorted(items, key=lambda item: (item["name"] != "AHU_annual.csv", item["name"], item["dataset_id"]))


@lru_cache(maxsize=4)
def read_verified(path, digest, signature):
    try:
        content = path.read_bytes()
        current_signature = file_signature(path.stat())
    except FileNotFoundError:
        fail(404, "MISSING_SOURCE", "The registered raw CSV is missing")
    if current_signature != signature or hashlib.sha256(content).hexdigest() != digest:
        fail(409, "SOURCE_INTEGRITY", "Raw CSV differs from the verified source slice")
    return source_frame(pd.read_csv(io.BytesIO(content), float_precision="round_trip"))


def file_signature(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=64)
def verify_file(path, expected, signature):
    with path.open("rb") as stream:
        before = file_signature(fstat(stream.fileno()))
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
        after = file_signature(fstat(stream.fileno()))
    if before != signature or after != signature or actual != expected:
        fail(409, "SOURCE_INTEGRITY", "Raw CSV or frozen Parquet differs from its registered SHA-256")


def parquet_window(source, start, limit):
    derivation = source["parquet_derivation"]
    processed = (settings.data_dir / "processed").resolve()
    path = (settings.data_dir / derivation["path"]).resolve()
    if path.parent != processed or derivation["source_sha256"] != source["sha256"]:
        fail(409, "DERIVATION_INTEGRITY", "Frozen Parquet does not match the registered raw CSV")
    try:
        stream = path.open("rb")
    except FileNotFoundError:
        return None
    with stream:
        signature = file_signature(fstat(stream.fileno()))
        try:
            verify_file(path, derivation["sha256"], signature)
        except FileNotFoundError:
            fail(409, "MISSING_DERIVATION", "Frozen annual Parquet disappeared")
        parquet = pq.ParquetFile(stream)
        metadata = parquet.schema_arrow.metadata or {}
        if (metadata.get(b"source_sha256") != source["sha256"].encode()
                or metadata.get(b"derivation") != derivation["format"].encode()
                or parquet.metadata.num_rows != source["rows"]):
            fail(409, "DERIVATION_INTEGRITY", "Frozen Parquet source identity or coverage mismatch")
        columns = parquet.schema_arrow.names
        empty = pd.DataFrame(columns=[name for name in columns if name != "Datetime"],
                             index=pd.DatetimeIndex([], name="Datetime"))
        if limit == 0:
            return empty
        timestamp_column = columns.index("Datetime")
        last_stamps = [parquet.metadata.row_group(i).column(timestamp_column).statistics.max
                       for i in range(parquet.num_row_groups)]
        group = 0 if start is None else bisect_left(last_stamps, start)
        if group == parquet.num_row_groups:
            return empty
        table = parquet.read_row_group(group)
        first = start_index(pd.DatetimeIndex(table["Datetime"].to_pandas()), start)
        # Keep the preceding sample for gap_before and one successor for next_start.
        tables = []
        if first == 0 and group > 0:
            previous = parquet.read_row_group(group - 1)
            tables.append(previous.slice(previous.num_rows - 1))
        tables.append(table)
        needed = first + limit + 1 - table.num_rows
        while needed > 0 and group + 1 < parquet.num_row_groups:
            group += 1
            table = parquet.read_row_group(group)
            tables.append(table)
            needed -= table.num_rows
        if file_signature(fstat(stream.fileno())) != signature:
            fail(409, "DERIVATION_INTEGRITY", "Frozen Parquet changed during the window read")
        return pa.concat_tables(tables).to_pandas().set_index("Datetime")


def annual_csv_window(path, signature, start, limit):
    # Existing DATA_ROOTs can be used before the frozen Parquet is installed.
    try:
        with path.open("rb") as stream:
            if file_signature(fstat(stream.fileno())) != signature:
                fail(409, "SOURCE_INTEGRITY", "Raw CSV changed before the window read")
            if limit == 0:
                return source_frame(pd.read_csv(stream, nrows=0))
            return read_annual_csv_window(stream, signature, start, limit)
    except FileNotFoundError:
        fail(404, "MISSING_SOURCE", "The registered raw CSV is missing")


def read_annual_csv_window(stream, signature, start, limit):
    selected = []
    previous = None
    count = 0
    with pd.read_csv(stream, chunksize=2048, float_precision="round_trip") as chunks:
        for chunk in chunks:
            frame = source_frame(chunk)
            first = start_index(frame.index, start)
            if first == len(frame):
                previous = frame.tail(1)
                continue
            if not selected:
                preceding = frame.iloc[first - 1:first] if first else previous
                if preceding is not None:
                    selected.append(preceding)
            window = frame.iloc[first:first + limit + 1 - count]
            selected.append(window)
            count += len(window)
            if count >= limit + 1:
                break
    if file_signature(fstat(stream.fileno())) != signature:
        fail(409, "SOURCE_INTEGRITY", "Raw CSV changed during the window read")
    return pd.concat(selected) if selected else frame.iloc[:0]


def dataset_data(dataset_id, start=None, limit=0, *, require_index=False):
    if dataset_id == DEMO_ID:
        source = demo_manifest()
        path = DEMO_DIR / "mixing-demo.csv"
        try:
            signature = file_signature(path.stat())
        except FileNotFoundError:
            fail(409, "SOURCE_INTEGRITY", "The registered synthetic source is missing")
        return source, read_verified(path, source["sha256"], signature)
    source = SOURCES.get(dataset_id)
    if source is None:
        fail(404, "UNKNOWN_DATASET", "Dataset is outside the verified runtime registry")
    path = source_path(source)
    try:
        stat = path.stat()
    except FileNotFoundError:
        fail(404, "MISSING_SOURCE", "The registered raw CSV is missing")
    signature = file_signature(stat)
    if "parquet_derivation" in source:
        try:
            verify_file(path, source["sha256"], signature)
        except FileNotFoundError:
            fail(404, "MISSING_SOURCE", "The registered raw CSV is missing")
        frame = parquet_window(source, start, limit)
        if frame is None and require_index:
            fail(409, "MISSING_DERIVATION", "Annual incident windows require the frozen Parquet")
        if frame is None:
            frame = annual_csv_window(path, signature, start, limit)
        return source, frame
    return source, read_verified(path, source["sha256"], signature)


def signal_catalog(frame, panel):
    return [{
        "canonical_id": key,
        "source_column": spec["source_column"],
        "kind": spec["kind"],
        "unit": spec["unit"],
        "source_unit": spec["source_unit"],
        "value_status": spec.get("value_status", "AS_DOCUMENTED"),
        "warning_code": spec.get("warning_code"),
        "origin": "BASIC" if spec["basic_eligible"] else "EXTRA_SIMULATED",
        "availability": "AVAILABLE" if spec["source_column"] in frame else "UNAVAILABLE",
    } for key, spec in SIGNALS.items() if panel == "EXTRA" or spec["basic_eligible"]]


def normalize(series, spec):
    values = pd.to_numeric(series, errors="coerce").replace([float("inf"), float("-inf")], float("nan"))
    if spec["source_unit"] == "degF":
        values = (values - 32) * (5 / 9)
    return [None if pd.isna(value) else float(value) for value in values]


def series_window(frame, panel, signal_ids, start, limit):
    catalog = {item["canonical_id"]: item for item in signal_catalog(frame, panel)}
    forbidden = set(signal_ids) - catalog.keys()
    if forbidden:
        fail(422, "SIGNAL_NOT_IN_PANEL", ", ".join(sorted(forbidden)))
    first = start_index(frame.index, start)
    end = min(first + limit, len(frame))
    window = frame.iloc[first:end]
    # Include the preceding sample to preserve gaps across pagination.
    steps = frame.index[max(0, first - 1):end].to_series().diff().dt.total_seconds()
    steps = steps.iloc[-len(window):] if len(window) else steps.iloc[:0]
    return {
        "clock_kind": CLOCK_KIND,
        "sample_seconds": SAMPLE_SECONDS,
        "timestamps": [stamp.isoformat() for stamp in window.index],
        "gap_before": [bool(gap) for gap in steps.gt(SAMPLE_SECONDS)],
        "next_start": frame.index[end].isoformat() if end < len(frame) else None,
        "signals": [{
            "canonical_id": key,
            "availability": catalog[key]["availability"],
            "value_status": catalog[key]["value_status"],
            "warning_code": catalog[key]["warning_code"],
            "values": normalize(window[SIGNALS[key]["source_column"]], SIGNALS[key])
            if catalog[key]["availability"] == "AVAILABLE" else [None] * len(window),
        } for key in signal_ids],
    }


def mode_input_window(dataset_id, start, limit, *, require_index=False):
    history = timedelta(seconds=HOLD_SECONDS)
    lower = max(start, datetime.min + history) - history if start is not None else None
    return dataset_data(dataset_id, lower, limit + HOLD_SECONDS // SAMPLE_SECONDS, require_index=require_index)


def mode_contexts(frame, first, end):
    history_first = max(0, first - HOLD_SECONDS // SAMPLE_SECONDS)
    # Restrict inference to two documented BASIC points even in the EXTRA panel.
    inputs = frame.iloc[history_first:end].reindex(columns=["SF_SPD_DM", "OA_TEMP"])
    contexts = evaluate_modes(
        (stamp, {"SF_SPD_DM": fan, "OA_TEMP": oat})
        for stamp, fan, oat in inputs.itertuples(name=None)
    )
    return contexts[first - history_first:]


def mode_segments(source, frame, start, limit):
    first = start_index(frame.index, start)
    end = min(first + limit, len(frame))
    segments = []
    summary = {"samples": end - first, "gaps": 0, "off_grid_steps": 0, "missing_samples": 0}
    for index, context in enumerate(mode_contexts(frame, first, end), start=first):
        stamp = frame.index[index]
        previous = frame.index[index - 1] if index else None
        quality = time_quality(previous, stamp)
        summary["gaps"] += quality["gap_before"]
        summary["off_grid_steps"] += quality["off_grid_before"]
        summary["missing_samples"] += quality["missing_samples_before"]
        state = {"mode": context.fan_state, "weather_context": context.economizer_band}
        timestamp = stamp.isoformat()
        if (not segments or quality["gap_before"] or quality["off_grid_before"]
                or any(segments[-1][key] != value for key, value in state.items())):
            segments.append({**state, "first": timestamp, "last": timestamp,
                             "samples": 1, "gap_before": quality["gap_before"],
                             "off_grid_before": quality["off_grid_before"]})
        else:
            segments[-1]["last"] = timestamp
            segments[-1]["samples"] += 1
    return {
        "result_origin": result_origin(source),
        "clock_kind": CLOCK_KIND,
        "sample_seconds": SAMPLE_SECONDS,
        "source_sha256": source["sha256"],
        "mode_policy": MODE_POLICY,
        "physical_context": PHYSICAL_CONTEXT,
        "time_quality": summary,
        "next_start": frame.index[end].isoformat() if end < len(frame) else None,
        "segments": segments,
    }


def evaluate_point(source, row, timestamp, panel, mode=None, previous=None):
    stamp = datetime.fromisoformat(timestamp)
    if mode is None:
        mode = evaluate_modes([(stamp, row)])[0]
    quality = signal_quality(row, signal_catalog(row, panel))
    quality_by_id = {item["canonical_id"]: item["flags"] for item in quality}
    timing = time_quality(previous, stamp)
    prerequisites = {
        "sat-tracking": ["MECHANICAL_COOLING_ENABLE"],
        "valve-tracking": ["VALIDATED_SIMULATION_VALVE_TRACKING_CONTEXT"],
    }
    workers = []
    for method, required in METHODS:
        excluded = [key for key in required if key not in quality_by_id]
        missing = [key for key in required if "MISSING_COLUMN" in quality_by_id.get(key, [])]
        invalid = [key for key in required if key not in missing and quality_by_id.get(key)]
        decision = assess(method, row, mode, missing, excluded, invalid)
        roots = []
        for key in required:
            spec = SIGNALS[key]
            column = spec["source_column"]
            if key in quality_by_id and column in row:
                roots.append({
                    "evidence_id": f"{source['sha256']}:{timestamp}:{key}",
                    "source_sha256": source["sha256"],
                    "source_column": column,
                    "canonical_id": key,
                    "origin": "BASIC" if spec["basic_eligible"] else "EXTRA_SIMULATED",
                    "timestamp": timestamp,
                    "value": normalize(pd.Series([row[column]]), spec)[0],
                    "unit": spec["unit"],
                })
        workers.append({
            "method_id": method, "method_version": "1.0.0",
            "method_status": decision.status, "reason_code": decision.reason, "predicate": decision.predicate,
            "missing_signal_ids": [key for key in required if key in missing or key in excluded],
            "invalid_signal_ids": invalid,
            "unverified_prerequisites": prerequisites.get(method, []),
            "roots": roots,
        })

    anomaly, display = {
        "VIOLATED": ("DETECTED", "ALARM"),
        "NOT_VIOLATED": ("NOT_DETECTED_IN_EVALUATED_TESTS", "NO_ALARM"),
        "INDETERMINATE": ("UNASSESSED", "NOT_EVALUABLE"),
    }[workers[0]["predicate"]]
    return {
        "result_origin": result_origin(source),
        "clock_kind": CLOCK_KIND,
        "timestamp": timestamp,
        "source_sha256": source["sha256"],
        "mode": mode.fan_state,
        "fan_on": mode.fan_on,
        "weather_context": mode.economizer_band,
        "mode_policy": MODE_POLICY,
        "physical_context": PHYSICAL_CONTEXT,
        "data_status": "DEGRADED" if timing["gap_before"] or timing["off_grid_before"] or any(
            item["flags"] for item in quality
        ) else "VALID",
        "time_quality": timing,
        "signal_quality": quality,
        "symptom_evaluation": point_result(row, mode.fan_state, SIGNALS, source["sha256"], timestamp),
        "anomaly_status": anomaly,
        "display_state": display,
        "cause_status": "NOT_ASSESSED",
        "issue_class": "SIGNAL_RANGE_VIOLATION" if anomaly == "DETECTED" else None,
        "model_scope": "UNKNOWN",
        "model_status": "UNAVAILABLE",
        "methods": workers,
    }
