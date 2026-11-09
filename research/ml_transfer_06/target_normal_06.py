"""One approved, read-only G36 reference evaluation using frozen Stage 05 artifacts."""
import argparse
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import platform
import stat

import numpy as np
import pandas as pd

from research.ml_transfer_05.contract import (
    FEATURES, PROTOCOL_SHA, TEMPERATURES, ContractError, block_rows, consecutive_true,
    input_support, reject_alias, sha, temperatures, validate_bindings,
)

ROLE = "target_reference"
PASS = "PASS_TARGET_NORMAL_AWAITING_FAULT_APPROVAL"
STOP = "STOP_OOD_HEALTHY"
METHODS = ("lightgbm_reduced", "ridge_reduced", "sat_minus_sp")
SOURCE = "AHU_annual.csv"
NORMAL = "BaselineSystem.csv"
FIT = "SOURCE_FIT_RECEIPT.json"
NATIVE = "REDUCED_SAT.lightgbm.txt"
RIDGE = "REDUCED_SAT_RIDGE.json"
PROTOCOL = Path(__file__).parents[1] / "ml_transfer_05" / "TRANSFER_05_PROTOCOL.json"
PINNED = {
    PROTOCOL.name: PROTOCOL_SHA,
    SOURCE: "13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b",
    NORMAL: "624e3c4e823e265e98d7c982f8498718b263ab1aff4d3fb4f2eb5ff787d370b3",
    FIT: "1187a8aa96ff7c64ef4e4c0613bee91e8acf5d3bbc794c7d314889ee451fff84",
    NATIVE: "643f08b6f50edef8487783f41ea7067e9863c83c9860181df4eda152d5751625",
    RIDGE: "a0e122b112ad2ae6b914635bf161d8977b5a11283b75260b620504dfd317f7de",
}
PREDICTION_COLUMNS = {
    "lightgbm_reduced": "LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF",
    "ridge_reduced": "RIDGE_SOURCE_TRAINED_PREDICTION_degF",
    "sat_minus_sp": "ACTIVE_SAT_SETPOINT_degF",
}
RESIDUAL_COLUMNS = {
    "lightgbm_reduced": "LIGHTGBM_ABS_RESIDUAL_degF",
    "ridge_reduced": "RIDGE_ABS_RESIDUAL_degF",
    "sat_minus_sp": "SAT_MINUS_SETPOINT_ABS_RESIDUAL_degF",
}


def checked(path, name, read_bytes=True):
    # Disallow a symlink, pipe, or device standing in for an approved basename.
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ContractError(f"STOP_SHA_MISMATCH:{name}:NOT_REGULAR")
        content = path.read_bytes() if read_bytes else None
        actual = sha256(content).hexdigest() if content is not None else sha(path)
    except OSError as error:
        raise ContractError(f"STOP_SHA_MISMATCH:{name}:UNREADABLE") from error
    if actual != PINNED[name]:
        raise ContractError(f"STOP_SHA_MISMATCH:{name}")
    return content


def verify_inputs(role, inputs, artifacts):
    if role != ROLE:
        raise ContractError("STOP_ROLE_NOT_AUTHORIZED")
    protocol = checked(PROTOCOL, PROTOCOL.name)
    checked(inputs / SOURCE, SOURCE, read_bytes=False)
    # These literal basenames are the entire allowlist. No directory discovery.
    return {
        PROTOCOL.name: protocol, FIT: checked(artifacts / FIT, FIT),
        NATIVE: checked(artifacts / NATIVE, NATIVE), RIDGE: checked(artifacts / RIDGE, RIDGE),
        NORMAL: checked(inputs / NORMAL, NORMAL),
    }


def checked_receipt(protocol, receipt):
    validate_bindings(protocol)
    spec = protocol["files"][ROLE]
    rule = protocol["calibration"]
    if (spec["name"] != NORMAL or spec["sha256"] != PINNED[NORMAL]
            or receipt["scope"] != "SOURCE_NORMAL_ONLY"
            or receipt["protocol_sha256"] != PROTOCOL_SHA or receipt["source_sha256"] != PINNED[SOURCE]
            or tuple(receipt["feature_order"]) != FEATURES
            or any(receipt["artifacts"][name] != PINNED[name] for name in (NATIVE, RIDGE))
            or (rule["alarm_operator"], rule["alarm_z"]) != (">", 3)):
        raise ContractError("FROZEN_RECEIPT_INCONSISTENT")
    if set(receipt["train_support_degF"]) != set(FEATURES):
        raise ContractError("INVALID_TRAIN_SUPPORT")
    for bounds in receipt["train_support_degF"].values():
        if len(bounds) != 2 or not np.isfinite(bounds).all() or bounds[0] >= bounds[1]:
            raise ContractError("INVALID_TRAIN_SUPPORT")
    if set(receipt["calibration"]) != set(METHODS):
        raise ContractError("INVALID_FROZEN_CALIBRATION")
    for params in receipt["calibration"].values():
        if (not np.isfinite([params["center"], params["scale"]]).all() or params["center"] < 0
                or params["scale"] <= rule["minimum_scale"] or params["days"] < rule["minimum_evaluated_days"]):
            raise ContractError("INVALID_FROZEN_CALIBRATION")


def load_ridge(content):
    artifact = json.loads(content)
    if tuple(artifact["feature_order"]) != FEATURES:
        raise ContractError("INVALID_RIDGE_FEATURE_ORDER")
    mean, scale, coefficient = (np.array(artifact[key], dtype=float) for key in ("mean", "scale", "coefficient"))
    intercept = float(artifact["intercept"])
    if (any(values.shape != (len(FEATURES),) or not np.isfinite(values).all()
            for values in (mean, scale, coefficient)) or np.any(scale <= 0) or not np.isfinite(intercept)):
        raise ContractError("INVALID_RIDGE_DIMENSIONS_OR_SCALE")
    return mean, scale, coefficient, intercept


def load_native(content):
    from lightgbm import Booster

    model = Booster(model_str=content.decode())
    if model.num_feature() != len(FEATURES) or tuple(model.feature_name()) != FEATURES:
        raise ContractError("INVALID_NATIVE_FEATURE_ORDER")
    return model


def clock_blocks(clock, protocol):
    rule = protocol["mask"]
    start, step = rule["target_block_anchor_model_s"], rule["step_s"]
    size = rule["minutes_per_block"] * rule["target_complete_blocks"]
    expected = start + step * np.arange(size + 1)
    actual = pd.to_numeric(clock, errors="coerce").to_numpy()
    if not np.array_equal(actual, expected):
        raise ContractError("UNQUALIFIED_CLOCK_OR_BLOCK_BOUNDARY")
    return expected[:-1], pd.Series(np.arange(size) // rule["minutes_per_block"])


def read_normal(content, protocol):
    spec = protocol["files"][ROLE]
    bindings = {binding["target"]: name for name, binding in protocol["bindings"].items()}
    mode_header = protocol["audit_only"]["target_cooling_mode"]["header"]
    needed = [spec["clock"], *bindings, mode_header]
    if not set(needed) <= set(pd.read_csv(BytesIO(content), nrows=0).columns):
        raise ContractError("MISSING_REQUIRED_TARGET_CHANNEL")
    raw = pd.read_csv(BytesIO(content), usecols=needed, float_precision="round_trip")
    seconds, labels = clock_blocks(raw[spec["clock"]], protocol)
    raw = raw.iloc[:len(seconds)]
    channels = raw[list(bindings)].rename(columns=bindings).apply(pd.to_numeric, errors="coerce")
    converted = temperatures(channels, False, protocol)
    invalid_unit_or_range = (channels[list(TEMPERATURES)].notna() & converted.isna()).any(axis=1)
    channels[list(TEMPERATURES)] = converted
    channels["SF_STATUS"] = channels.SF_STATUS.where(channels.SF_STATUS.isin([0, 1]))
    mode = pd.to_numeric(raw[mode_header], errors="coerce")
    mode = mode.where(mode.isin(protocol["audit_only"]["target_cooling_mode"]["known_codes"]))
    reject_alias(channels)
    return seconds, labels, channels, mode, invalid_unit_or_range


def prepare_trace(seconds, labels, channels, mode, invalid_unit_or_range, protocol, limits):
    rule = protocol["mask"]
    running = consecutive_true(channels.SF_STATUS.eq(1).to_numpy()) >= rule["fan_hold_s"] // rule["step_s"] + 1
    warm = channels.OA_TEMP.gt(protocol["audit_only"]["source_bands"]["warm_above_degF"]).to_numpy()
    denominator = running & warm
    finite = np.isfinite(channels).all(axis=1).to_numpy()
    supported = input_support(channels, limits)
    known_mode = mode.notna().to_numpy()
    ready = denominator & finite & supported & known_mode & ~invalid_unit_or_range.to_numpy()
    reject_alias(channels, ready)
    tech = channels.SF_STATUS.isna() | channels.OA_TEMP.isna() | mode.isna() | invalid_unit_or_range
    failure = bool(tech.any())
    trace = pd.DataFrame({
        "csv_row_1based": np.arange(len(seconds)) + 2, "model_seconds": seconds, "block": labels,
        "SAT_MEASURED_SIMULATED_BAS_degF": channels.SA_TEMP, "MA_TEMP_degF": channels.MA_TEMP,
        "OA_TEMP_degF": channels.OA_TEMP, "RA_TEMP_degF": channels.RA_TEMP,
        "ACTIVE_SAT_SETPOINT_degF": channels.SA_TEMPSPT, "FAN_STATUS": channels.SF_STATUS,
        "PLANT_MODE": mode.astype("Int64"), "RUNNING": running, "WARM": warm, "RUNNING_WARM": denominator,
        "SOURCE_SUPPORT": supported, "MINUTE_ELIGIBLE": ready, "ELIGIBLE": False,
        "INVALID_UNIT_OR_RANGE": invalid_unit_or_range,
        "ABSTAIN_REASON": np.select(
            [channels.SF_STATUS.isna(), channels.OA_TEMP.isna(), ~known_mode, invalid_unit_or_range,
             ~running, ~warm, ~finite, ~supported],
            ["UNKNOWN_FAN", "UNKNOWN_OAT", "UNKNOWN_PLANT_MODE", "INVALID_UNIT_OR_RANGE",
             "NOT_RUNNING_OR_HOLD", "NOT_WARM", "MISSING_REQUIRED_CHANNEL", "OUTSIDE_SOURCE_SUPPORT"], default=""),
    })
    blocks = []
    for block, positions, details in block_rows(labels, denominator, ready, protocol):
        if failure or details["status"] == "ABSTAIN":
            trace.loc[positions, "ABSTAIN_REASON"] = "TECHNICAL_STOP" if failure else "INSUFFICIENT_BLOCK_COVERAGE"
        else:
            trace.loc[positions, "ELIGIBLE"] = True
        blocks.append(details)
    return trace, blocks, failure


def summaries(trace, blocks, receipt, protocol):
    summaries = []
    for block, details in enumerate(blocks):
        ticks = trace[trace.block == block]
        usable = ticks[ticks.ELIGIBLE]
        total = details["warm_running_minutes"]
        row = {
            "block": block, "start_model_s": int(ticks.model_seconds.iloc[0]),
            "end_exclusive_model_s": int(ticks.model_seconds.iloc[-1] + protocol["mask"]["step_s"]),
            "calendar_minutes": len(ticks), "warm_running_minutes": total,
            "eligible_before_block_gate": details["usable_minutes"], "eligible_minutes": len(usable),
            "coverage": len(usable) / total if total else None,
            "calendar_coverage": len(usable) / len(ticks),
            "max_contiguous_candidate_minutes": details["longest_run"],
            "max_contiguous_scored_minutes": int(consecutive_true(ticks.ELIGIBLE.to_numpy()).max()),
            "fan_missing": int(ticks.FAN_STATUS.isna().sum()), "oat_missing": int(ticks.OA_TEMP_degF.isna().sum()),
            "plant_mode_missing": int(ticks.PLANT_MODE.isna().sum()),
            "invalid_unit_or_range": int(ticks.INVALID_UNIT_OR_RANGE.sum()),
            "warm_running_outside_support": int((ticks.RUNNING_WARM & ~ticks.SOURCE_SUPPORT).sum()),
            "status": "EVALUATED" if len(usable) else "ABSTAIN",
        }
        for mode in (1, 2, 3, 4):
            row[f"mode_{mode}_minutes"] = int(ticks.PLANT_MODE.eq(mode).sum())
            row[f"mode_{mode}_eligible"] = int(usable.PLANT_MODE.eq(mode).sum())
        for method, column in RESIDUAL_COLUMNS.items():
            mae = float(usable[column].mean()) if len(usable) else None
            calibration = receipt["calibration"][method]
            z = (mae - calibration["center"]) / calibration["scale"] if mae is not None else None
            row[method + "_mae_degF"] = mae
            row[method + "_z"] = z
            row[method + "_decision"] = "ABSTAIN" if z is None else "ALERT" if z > 3 else "NO_ALERT"
        summaries.append(row)
    return summaries


def evaluate_normal(decoded, model, ridge, receipt, protocol):
    seconds, labels, channels, mode, invalid_range = decoded
    trace, blocks, technical_stop = prepare_trace(
        seconds, labels, channels, mode, invalid_range, protocol, receipt["train_support_degF"])
    eligible = trace.ELIGIBLE
    for column in (*RESIDUAL_COLUMNS.values(), PREDICTION_COLUMNS["lightgbm_reduced"], PREDICTION_COLUMNS["ridge_reduced"]):
        trace[column] = np.nan
    if eligible.any():
        x = channels.loc[eligible, list(FEATURES)]
        mean, scale, coefficient, intercept = ridge
        predicted = {
            "lightgbm_reduced": model.predict(x, validate_features=True, num_threads=1),
            "ridge_reduced": ((x.to_numpy() - mean) / scale) @ coefficient + intercept,
            "sat_minus_sp": channels.loc[eligible, "SA_TEMPSPT"].to_numpy(),
        }
        actual = channels.loc[eligible, "SA_TEMP"].to_numpy()
        for method, prediction in predicted.items():
            if prediction.shape != actual.shape or not np.isfinite(prediction).all():
                raise ContractError(f"INVALID_MODEL_PREDICTION:{method}")
            if method != "sat_minus_sp":
                trace.loc[eligible, PREDICTION_COLUMNS[method]] = prediction
            trace.loc[eligible, RESIDUAL_COLUMNS[method]] = np.abs(actual - prediction)
    rows = summaries(trace, blocks, receipt, protocol)
    return trace, rows, technical_stop


def window_summary(trace, rows, technical_stop, protocol):
    total = int(trace.RUNNING_WARM.sum())
    used = int(trace.ELIGIBLE.sum())
    evaluated = sum(row["status"] == "EVALUATED" for row in rows)
    method_summary = {}
    for method, column in RESIDUAL_COLUMNS.items():
        alarms = [row["block"] for row in rows if row[method + "_decision"] == "ALERT"]
        method_summary[method] = {
            "alarm_blocks": alarms, "false_alarm_rate_conditional": len(alarms) / evaluated if evaluated else None,
            "pooled_mae_degF": float(trace[column].mean()) if used else None,
            "daily_z": [row[method + "_z"] for row in rows],
        }
    alarms = len(method_summary["lightgbm_reduced"]["alarm_blocks"])
    rule = protocol["healthy_gate"]
    failures = [reason for failed, reason in (
        (technical_stop, "TECHNICAL_INPUT_OBSERVABILITY"),
        (evaluated < rule["minimum_evaluated_blocks"], "TOO_FEW_EVALUATED_BLOCKS"),
        (not total or used / total < rule["minimum_coverage"], "INSUFFICIENT_WINDOW_COVERAGE"),
        (alarms > rule["maximum_lightgbm_alarm_blocks"], "LIGHTGBM_NORMAL_ALARM"),
    ) if failed]
    status = STOP if failures else PASS
    counts = ["fan_missing", "oat_missing", "plant_mode_missing", "invalid_unit_or_range",
              "warm_running_outside_support", *(f"mode_{mode}_{metric}" for mode in (1, 2, 3, 4)
                                                for metric in ("minutes", "eligible"))]
    return {
        "gate": status, "gate_failed_conditions": failures, "calendar_blocks": len(rows), "evaluated_blocks": evaluated, "calendar_minutes": len(trace),
        "warm_running_minutes": total, "eligible_minutes": used,
        "coverage": used / total if total else None, "calendar_coverage": used / len(trace),
        "max_contiguous_scored_minutes": int(consecutive_true(trace.ELIGIBLE.to_numpy()).max()),
        **{key: sum(row[key] for row in rows) for key in counts},
        "abstain_reasons": {str(key): int(count) for key, count in trace.loc[~trace.ELIGIBLE, "ABSTAIN_REASON"].value_counts().items()},
        "methods": method_summary, "technical_input_stop": technical_stop,
    }


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def run(role, inputs, artifacts, output):
    if role != ROLE:
        raise ContractError("STOP_ROLE_NOT_AUTHORIZED")
    output.mkdir(parents=True, exist_ok=False)
    content = verify_inputs(role, inputs, artifacts)
    protocol, receipt = (json.loads(content[name]) for name in (PROTOCOL.name, FIT))
    checked_receipt(protocol, receipt)
    versions = {"python": platform.python_version(),
                **{name: version(name) for name in ("lightgbm", "pandas", "numpy")}}
    if any(value != protocol["versions"][name] for name, value in versions.items()):
        raise ContractError("SCORING_VERSIONS_NOT_PINNED")
    decoded = read_normal(content[NORMAL], protocol)
    ridge, model = load_ridge(content[RIDGE]), load_native(content[NATIVE])
    write_json(output / "RUN_STARTED.json", {
        "started_utc": datetime.now(timezone.utc).isoformat(), "role": role, "sha256": PINNED,
        "target_normal_only": True,
    })
    trace, rows, technical_stop = evaluate_normal(decoded, model, ridge, receipt, protocol)
    summary = window_summary(trace, rows, technical_stop, protocol)
    trace_path, block_path = output / "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz", output / "TARGET_NORMAL_06_BLOCKS.csv"
    with trace_path.open("xb") as stream, gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
        compressed.write(trace.to_csv(index=False).encode())
    pd.DataFrame(rows).to_csv(block_path, index=False, mode="x")
    write_json(output / "TARGET_NORMAL_06_RECEIPT.json", {
        "role": role, "source": NORMAL, "sha256": PINNED, "versions": versions,
        "ridge_runtime": "FROZEN_JSON_COEFFICIENTS_NUMPY",
        "features": list(FEATURES), "alarm_operator": ">", "alarm_z": 3,
        "calibration": receipt["calibration"], "source_support_degF": receipt["train_support_degF"],
        "clock_basis": "MODEL_SECONDS", "excluded_right_boundary_model_s": 18230400,
        "independent_normal_runs": 1, "target_fault_prediction_executed": False,
        "target_normal_native_predict_calls": int(trace.ELIGIBLE.any()),
        "fault_phase_authorized": False, "artifacts": {path.name: sha(path) for path in (trace_path, block_path)},
        **summary,
    })
    print(summary["gate"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    for name in ("inputs", "artifacts", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    try:
        run(**vars(parser.parse_args()))
    except ContractError as error:
        reason = str(error)
        gate = reason.split(":")[0] if reason.startswith("STOP_") else STOP
        parser.exit(2, json.dumps({"gate": gate, "reason": reason, "fault_phase_authorized": False}) + "\n")
