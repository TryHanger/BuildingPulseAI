"""Replay the eight pinned REPRO-02 boosters on the REPRO-01 BASIC test clock."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.services.sat_daily_coverage import POLICY_VERSION, assess
from backend.app.services.virtual_sensor_research import checked_payload, digest, native_model, registry
from research.ml_repro_02.controls import inputs
from research.ml_repro_02.gate import SOURCE_SHA, check
from research.ml_reproduction import run as v1
from research.ml_reproduction.sources import BASELINE, BIASES, CASES, sha

MANIFEST_SHA = "359afbe1d3022e64c52ec5e1d916bb731a8c4c45aef9a835d0c9ab6ba73c0734"
POLICY_SHA = "a8c62109991f3f5c3ebea3a5c8469d3cfcb8fb652c7c6f03742577abc9535c30"
D0_RECEIPT_SHA = "46f846f8159aa62619828c20e3b7a9146d3d97e51994e1ef736bed561ab69d88"
ARM = "PRODUCT_BASIC"
MINUTE = pd.Timedelta("1min")
TARGETS = ("SA_TEMP", "MA_TEMP", "RA_TEMP", *(f"ZONE_TEMP_{i}" for i in range(1, 6)))
REPRO01_DAILY_SHA = "daf7069f16da8e1fcbf28e9825c198b4e47ede103ddce92d42cec905b1cf2648"
METHODS = {
    "sat_only": "LightGBM.SA_TEMP",
    "system_max_8": "LightGBM.z",
    "sat_minus_setpoint": "SAT setpoint.z",
    "ridge": "Ridge.z",
    "pca_paper": "PCA-paper.z",
    "pca_input_matched": "PCA-input-matched.z",
}


def timestamp_digest(clock):
    return digest(clock.as_unit("ns").asi8.astype("<i8").tobytes())


def mask_receipt(clock, mask):
    mask = np.asarray(mask, dtype=np.uint8)
    return {"first_source_tick": str(clock[0]), "last_source_tick": str(clock[-1]),
            "calendar_minutes": len(mask), "eligible_minutes": int(mask.sum()),
            "mask_sha256": digest(mask.tobytes()),
            "eligible_timestamp_sha256": timestamp_digest(clock[mask.astype(bool)])}


def prepare(frame, raw):
    missing = sorted(set(["Datetime", *raw]) - set(frame.columns))
    if missing:
        raise ValueError("MISSING_BASIC_CHANNELS: " + ", ".join(missing))
    clock = pd.DatetimeIndex(frame.Datetime)
    if (clock.tz is not None or clock.hasnans or not clock.is_monotonic_increasing or
            not (np.diff(clock.as_unit("ns").asi8) == MINUTE.value).all() or not (clock == clock.floor("min")).all()):
        raise ValueError("INVALID_SOURCE_CLOCK")
    if not frame.SF_SPD_DM.isin([0, 1]).all():
        raise ValueError("UNKNOWN_FAN_TIMELINE")
    running = v1.fan_running(clock, frame.SF_SPD_DM)
    prepared, mask = v1.prepare(frame, ARM, raw)
    return prepared, pd.Series(mask, index=clock), pd.Series(running, index=clock)


def score(frame, boosters, entries):
    output = {"sat_minus_setpoint": (frame.SA_TEMP - frame.SA_TEMPSPT).abs()}
    for target, model in boosters.items():
        entry = entries[target]
        prediction = model.predict(frame[entry["feature_order"]], validate_features=True, num_threads=4)
        output[target] = v1.zscore(np.abs(frame[target].to_numpy() - prediction), entry["abs_center"], entry["abs_scale"])
    minute = pd.DataFrame(output, index=frame.index)
    if not np.isfinite(minute).all(axis=None):
        raise ValueError("NONFINITE_NATIVE_PREDICTION_OR_CALIBRATION")
    return minute


def historical_lookup(path):
    check(path, REPRO01_DAILY_SHA)
    daily = pd.read_csv(path, float_precision="round_trip")
    return daily.set_index(["scenario", "day", "model"]).to_dict("index")


def rows(days, member, paired_member, minute, running, historical, audit, sat_cal, matched):
    label = CASES[member][0]
    for day in days:
        date = str(day.date())
        next_day = day + pd.Timedelta("1D")
        points = minute.loc[day:next_day - MINUTE]
        running_count = int(running.loc[day:next_day - MINUTE].sum())
        coverage = assess(points.index.hour * 60 + points.index.minute, running_count)
        old = historical.get((label, date, "LightGBM"))
        original_ticks = old["ticks"] if old else 0
        if not matched and original_ticks != len(points):
            raise ValueError(f"Historical mask size divergence for {member} {date}")
        # The matched set is a subset of the reconstructed original minute mask.
        # Equal sizes therefore certify exact equality, not just coincident coverage.
        original_mask = original_ticks == len(points)
        record = {
            "scope": "MATCHED_MINUTES" if matched else "ORIGINAL_ARM_MASK", "pair_member": paired_member,
            "member": member, "scenario": label, "day": date, "calendar_minutes": 1440,
            "member_sha256": audit["members"][member]["sha256"], "source_sha256": SOURCE_SHA,
            "alias_status": "UNVERIFIED_PUBLISHER_ALIAS" if member in BIASES else
                            "PUBLISHER_BASELINE" if member == BASELINE else "NO_BIAS_ALIAS_APPLIED",
            "source_clock": "SOURCE_LOCAL_UNVERIFIED_UTC_OFFSET",
            "usable_minutes": len(points), "running_minutes": running_count,
            "usable_timestamps_sha256": timestamp_digest(points.index),
            "calendar_coverage": len(points) / 1440,
            "running_coverage": len(points) / running_count if running_count else None,
            "continuous_minutes": coverage.continuous_minutes, "policy": POLICY_VERSION,
            "policy_status": coverage.status, "policy_reason": coverage.reason,
            "historical_comparators_mask_equal": original_mask,
        }
        if points.empty:
            yield record
            continue
        mean = points.mean()
        z = {"sat_only": float(mean.SA_TEMP), "system_max_8": float(mean[list(TARGETS)].max()),
             "sat_minus_setpoint": float((mean.sat_minus_setpoint - sat_cal[0]) / sat_cal[1])}
        record["sat_minus_setpoint_raw_f"] = float(mean.sat_minus_setpoint)
        record.update({f"native_target_{target}": float(mean[target]) for target in TARGETS})
        for method, field in METHODS.items():
            old_method, column = field.split(".")
            if original_mask:
                saved = historical[label, date, old_method]
                if saved["ticks"] != len(points):
                    raise ValueError(f"Historical comparator mask size divergence for {method}")
                z.setdefault(method, saved[column])
                if pd.notna(saved[column]):
                    record[f"{method}_repro01_z"] = saved[column]
            value = z.get(method)
            if value is not None and np.isfinite(value):
                record[f"{method}_z"] = value
                record[f"{method}_historical_alarm"] = bool(value > 3)
                if coverage.status == "EVALUATED":
                    record[f"{method}_policy_z"] = value
                    record[f"{method}_policy_alarm"] = bool(value > 3)
        yield record


def replay(archive, d0, review, output):
    check(archive, SOURCE_SHA)
    check(Path(__file__).with_name("SAT_DAILY_COVERAGE_V1.md"), POLICY_SHA)
    registry_root, manifest, meta = registry(review / "registry", MANIFEST_SHA)
    check(review / "p1-gate.json", manifest["p1_gate_sha256"])
    check(review / "overlay/research/ml_repro_02/PROTOCOL.yaml", manifest["integration_protocol_sha256"])
    for package in ("lightgbm", "pandas", "numpy", "pyarrow"):
        if version(package) != meta.versions[package]:
            raise ValueError(f"Frozen replay dependency mismatch: {package}")
    columns, graph, signal_map, params = inputs(d0, review / "reference_v1/official.ttl")
    features, raw, _ = v1.plans(graph, columns, signal_map, ARM)
    if (features != manifest["schema"]["feature_orders"] or raw != meta.available_channels or
            params != manifest["lightgbm_parameters"] or manifest["seed"] != 42):
        raise ValueError("Frozen training schema, parameters or seed mismatch")
    receipt_path = d0 / "verified.json"
    check(receipt_path, D0_RECEIPT_SHA)
    receipt = json.loads(receipt_path.read_text())
    audit_path = d0 / "source-audit.json"
    check(audit_path, receipt["accepted_receipt_sha256"])
    check(review / "reference_v1/source-audit.json", receipt["accepted_receipt_sha256"])

    def load(member):
        path = d0 / "cache" / f"{member}.parquet"
        check(path, receipt["cache"][path.name])
        return pd.read_parquet(path, columns=["Datetime", *raw])

    audit = json.loads(audit_path.read_text())
    entries = manifest["models"]
    boosters = {target: native_model(checked_payload(registry_root, entry), tuple(features[target]),
                                    meta.versions["lightgbm"]) for target, entry in entries.items()}
    for member, expected in [(BASELINE, manifest["training_member_sha256"]),
                             *((case.member, case.member_sha256) for case in meta.cases)]:
        if audit["members"][member]["sha256"] != expected:
            raise ValueError(f"Source member mismatch: {member}")
    historical = historical_lookup(review / "reference_v1/experiments/PRODUCT_BASIC/daily.csv")
    healthy, eligible, running = prepare(load(BASELINE), raw)
    split1, split2 = v1.split(healthy, eligible, False)
    end = pd.Timestamp(meta.split["test_end_exclusive"])
    if str(split2) != meta.split["test_start"]:
        raise ValueError("Test cutoff mismatch")
    days = pd.date_range(split2, end - pd.Timedelta("1D"), freq="D")
    test_clock = pd.date_range(split2, end - MINUTE, freq="min")
    train = healthy.index < split1
    calibration = (healthy.index >= split1) & (healthy.index < split2)
    splits = {name: mask_receipt(healthy.index[period], eligible.loc[period])
              for name, period in (("train", train), ("calibration", calibration))}
    for name, period in (("train", train), ("calibration", calibration)):
        ticks = healthy.index[eligible & period]
        if (str(ticks[0]), str(ticks[-1]), str(len(ticks))) != tuple(meta.split[f"{name}_{key}"]
                                                                    for key in ("first", "last", "minutes")):
            raise ValueError(f"{name} eligible split divergence")
    cal = healthy.loc[eligible & calibration]
    cal_residual = (cal.SA_TEMP - cal.SA_TEMPSPT).abs()
    sat_cal = v1.calibration(v1.daily(cal_residual, cal.index)[0].to_numpy())
    if sat_cal[1] is None:
        raise ValueError("CONSTANT_CALIBRATION_SCALE")
    output_rows, masks, paired = [], {}, {}
    healthy_points = healthy_running = None
    for member in CASES:
        frame, mask, member_running = (healthy, eligible, running) if member == BASELINE else prepare(load(member), raw)
        test = (frame.index >= split2) & (frame.index < end)
        if not frame.index[test].equals(test_clock):
            raise ValueError(f"Test calendar not complete: {member}")
        masks[member] = {name: mask_receipt(test_clock, values.loc[test])
                         for name, values in (("eligible", mask), ("running", member_running))}
        points = score(frame.loc[mask & test], boosters, entries)
        output_rows.extend(rows(days, member, "", points, member_running, historical, audit, sat_cal, matched=False))
        if member == BASELINE:
            healthy_points, healthy_running = points, member_running
        else:
            common = healthy_points.index.intersection(points.index)
            paired[member] = mask_receipt(test_clock, test_clock.isin(common))
            output_rows.extend(rows(days, BASELINE, member, healthy_points.loc[common], healthy_running, historical,
                                    audit, sat_cal, matched=True))
            output_rows.extend(rows(days, member, member, points.loc[common], member_running, historical,
                                    audit, sat_cal, matched=True))
        print(f"Replayed {member}: {len(points)} eligible minutes on {len(days)} calendar days", flush=True)
    csv = output / "SCORE_PARITY_FULL_COHORT.csv"
    v1.write_table(csv, output_rows)
    (output / "SCORE_PARITY_METADATA.json").write_text(json.dumps({
        "scope": "SIMULATED_BENCHMARK", "use": "RESEARCH_ONLY", "arm": ARM,
        "model_manifest_sha256": MANIFEST_SHA, "native_models": entries, "source_sha256": SOURCE_SHA,
        "source_audit_sha256": sha(audit_path), "d0_receipt_sha256": D0_RECEIPT_SHA, "source_members": {member: audit["members"][member]["sha256"] for member in CASES},
        "legacy_daily_sha256": REPRO01_DAILY_SHA, "frozen_protocol_sha256": meta.protocol_sha256,
        "integration_protocol_sha256": meta.integration_protocol_sha256,
        "policy_sha256": POLICY_SHA, "policy_version": POLICY_VERSION, "split": meta.split, "split_masks": splits,
        "test_masks": masks, "paired_masks": paired, "schema": manifest["schema"], "schema_sha256": meta.schema_sha256,
        "temperature_unit": "degF (source-native, no conversion)", "source_timezone": meta.source_timezone,
        "seed": manifest["seed"], "parameters": params, "versions": meta.versions,
        "method_versions": {method.id: method.version for method in meta.methods},
        "saved_ridge_pca_version": "REPRO-01.v1 saved daily CSV", "sat_setpoint_daily_calibration": sat_cal,
        "csv_sha256": sha(csv), "calendar_days": len(days), "rows": len(output_rows),
    }, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "d0", "review", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if not args.archive.is_file():
        parser.exit(2, "BLOCKED_BY_SOURCE: full pinned SD-AHU ZIP required\n")
    args.output.mkdir(parents=True, exist_ok=False)
    replay(**vars(args))
