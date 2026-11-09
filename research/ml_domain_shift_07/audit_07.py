"""Descriptive audit of frozen source observations and saved target predictions only."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
from decimal import Decimal
import gzip
from hashlib import file_digest, sha256
from io import BytesIO
import json
from math import isclose, isfinite
from pathlib import Path
from statistics import correlation, fmean
from zipfile import ZipFile

ARCHIVE_05 = "2febd05cdfe42efb9dbe65c39a5b0f1c42a22c07fba657f691e33bcde2113b7b"
ARCHIVE_06 = "64ce1a8c46e163ae346df4d3bfec82d486d3a0052fc5da47a4cd2112a45e6bcf"
PROTOCOL_SHA = "7efbb52918b8ffb004318bf538fbe58774600aeefebe93cdaebc7ab72fee0fd0"
FIT_SHA = "1187a8aa96ff7c64ef4e4c0613bee91e8acf5d3bbc794c7d314889ee451fff84"
SOURCE_SHA = "13a61e5b3e62dcf214b387dc57632073a8044c794eb8102d90d074aa80702d8b"
TRACE = "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"
FEATURES = ("MA_TEMP", "OA_TEMP", "RA_TEMP")
SAT = "SAT_MEASURED_SIMULATED_BAS_degF"
SP = "ACTIVE_SAT_SETPOINT_degF"
PREDICTIONS = {
    "lightgbm_reduced": "LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF",
    "ridge_reduced": "RIDGE_SOURCE_TRAINED_PREDICTION_degF",
    "sat_minus_sp": SP,
}
RESIDUALS = {
    "lightgbm_reduced": "LIGHTGBM_ABS_RESIDUAL_degF",
    "ridge_reduced": "RIDGE_ABS_RESIDUAL_degF",
    "sat_minus_sp": "SAT_MINUS_SETPOINT_ABS_RESIDUAL_degF",
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def stats(values):
    return {"min": min(values), "mean": fmean(values), "max": max(values)}


def feature_summary(samples):
    return {
        "summary_degF": {name: stats(samples[name]) for name in FEATURES},
        "pairwise_pearson": {f"{a}/{b}": correlation(samples[a], samples[b])
                             for i, a in enumerate(FEATURES) for b in FEATURES[i + 1:]},
    }


def source_audit(path, protocol):
    check(sha(path) == SOURCE_SHA, "Source SHA mismatch")
    rules, window = protocol["mask"], protocol["partition"]
    samples = {name: [] for name in (*FEATURES, "SA_TEMP")}
    source_start, train_end = (datetime.fromisoformat(window[key]) for key in ("start", "train_end_exclusive"))
    hold = rules["fan_hold_s"] // rules["step_s"] + 1
    step = timedelta(seconds=rules["step_s"])
    warm_threshold = protocol["audit_only"]["source_bands"]["warm_above_degF"]
    low, high = protocol["units"]["valid_temperature_degF"]
    setpoints, previous, streak, count = Counter(), None, 0, 0
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            count += 1
            clock = datetime.fromisoformat(row["Datetime"])
            check(previous is None or clock - previous == step, "Source clock diverged")
            previous = clock
            streak = streak + 1 if float(row["SF_SPD_DM"]) == 1 else 0
            if not source_start <= clock < train_end or streak < hold or float(row["OA_TEMP"]) <= warm_threshold:
                continue
            temperature = {key: float(row[key]) for key in (*samples, "SA_TEMPSPT")}
            if not all(isfinite(value) and low <= value <= high for value in temperature.values()):
                continue
            for name in samples:
                samples[name].append(temperature[name])
            setpoints[Decimal(row["SA_TEMPSPT"])] += 1
    check(count == protocol["files"]["source"]["rows"], "Unexpected source row count")
    check(setpoints == {Decimal("55.184006"): 70842}, "Frozen training setpoint distribution diverged")
    return {"eligible_training_minutes": sum(setpoints.values()), "train_period": [window["start"], window["train_end_exclusive"]],
            "training_setpoint_support": {"unit": "degF", "span": [str(min(setpoints)), str(max(setpoints))],
                                          "unique_count": len(setpoints)},
            "setpoint_counts": {str(key): count for key, count in setpoints.items()},
            "sat_degF": stats(samples["SA_TEMP"]), "features": feature_summary(samples)}


def residuals(row, name):
    residual = float(row[RESIDUALS[name]])
    check(isclose(residual, abs(float(row[SAT]) - float(row[PREDICTIONS[name]])), abs_tol=1e-10),
          "Trace residual mismatch")
    return residual


def target_audit(content, saved_blocks, receipt, support):
    with gzip.open(BytesIO(content), "rt", newline="") as stream:
        rows = list(csv.DictReader(stream))
    check(len(rows) == 10080 and len(saved_blocks) == 7, "Wrong trace shape")
    for i, row in enumerate(rows):
        check(int(row["model_seconds"]) == 17625600 + 60 * i and int(row["block"]) == i // 1440,
              "Wrong trace clock")
    eligible = [row for row in rows if row["ELIGIBLE"] == "True"]
    check(len(eligible) == receipt["eligible_minutes"] == 5425, "Eligible denominator differs")
    check(all(row["SOURCE_SUPPORT"] == "True"
              and all(support[name][0] <= float(row[name + "_degF"]) <= support[name][1] for name in FEATURES)
              for row in eligible), "Frozen source support differs")
    mode_4 = [row for row in eligible if row["PLANT_MODE"] == "4"]
    check(len(mode_4) == receipt["mode_4_eligible"] == 6 and all(row["block"] == "6" for row in mode_4),
          "Unexpected mode 4 samples")
    methods = {}
    for name in PREDICTIONS:
        params = receipt["calibration"][name]
        daily_z, daily_mae = [], []
        for i, block in enumerate(saved_blocks):
            values = [residuals(row, name) for row in eligible if int(row["block"]) == i]
            mae = fmean(values)
            z = (mae - params["center"]) / params["scale"]
            check(isclose(z, float(block[name + "_z"]), abs_tol=1e-10), "Saved daily score differs")
            daily_z.append(z)
            daily_mae.append(mae)
        actual_alerts = sum(z > 3 for z in daily_z)
        check(actual_alerts == 7 and len(receipt["methods"][name]["alarm_blocks"]) == 7, "Alarm count differs")
        pooled = fmean(residuals(row, name) for row in eligible)
        check(isclose(pooled, receipt["methods"][name]["pooled_mae_degF"], abs_tol=1e-10), "MAE differs")
        remaining = [residuals(row, name) for row in eligible if row["block"] == "6" and row["PLANT_MODE"] != "4"]
        audit_mae = fmean(remaining)
        audit_z = (audit_mae - params["center"]) / params["scale"]
        methods[name] = {
            "alarm_blocks": actual_alerts, "mae_degF": pooled, "z_range": [min(daily_z), max(daily_z)],
            "source_daily_mae_alarm_threshold_degF": params["center"] + 3 * params["scale"],
            "audit_only_last_block": {"as_recorded_z": daily_z[-1], "without_mode_4_z": audit_z,
                                      "as_recorded_mae_degF": daily_mae[-1], "without_mode_4_mae_degF": audit_mae,
                                      "without_mode_4_would_exceed_frozen_threshold": audit_z > 3},
        }
    check(receipt["gate"] == "STOP_OOD_HEALTHY" and not receipt["fault_phase_authorized"]
          and not receipt["target_fault_prediction_executed"] and receipt["independent_normal_runs"] == 1,
          "Frozen gate or scope differs")
    return {
        "scope": "ONE_PREVIOUSLY_SCORED_G36_SIMULATED_NORMAL_RUN", "dependent_blocks": True,
        "external_field_validation": False, "calendar_minutes": len(rows), "eligible_minutes": len(eligible),
        "warm_running_minutes": receipt["warm_running_minutes"], "evaluated_blocks": receipt["evaluated_blocks"],
        "all_eligible_features_inside_frozen_1d_support": True, "mode_4_eligible_count": len(mode_4),
        "mode_4_eligible_model_seconds": [int(row["model_seconds"]) for row in mode_4],
        "mode_4_sensitivity_policy": "AUDIT_ONLY_NO_RESCORING_NO_GATE_CHANGE",
        "last_block_minutes_as_recorded": 775, "last_block_minutes_without_mode_4": 769,
        "sat_degF": stats([float(row[SAT]) for row in eligible]), "setpoint_degF": stats([float(row[SP]) for row in eligible]),
        "lightgbm_prediction_degF": stats([float(row[PREDICTIONS["lightgbm_reduced"]]) for row in eligible]),
        "features": feature_summary({name: [float(row[name + "_degF"]) for row in eligible] for name in FEATURES}),
        "methods": methods, "transfer_normal_gate": receipt["gate"], "target_fault_eval_allowed": False,
    }


def main(source, design_archive, normal_archive, output):
    check(sha(design_archive) == ARCHIVE_05 and sha(normal_archive) == ARCHIVE_06, "Accepted archive SHA differs")
    with ZipFile(design_archive) as design, ZipFile(normal_archive) as normal:
        protocol_bytes = design.read("TRANSFER_05_PROTOCOL.json")
        fit_bytes = design.read("source_fit/SOURCE_FIT_RECEIPT.json")
        check(sha256(protocol_bytes).hexdigest() == PROTOCOL_SHA and sha256(fit_bytes).hexdigest() == FIT_SHA,
              "Stage 05 freeze differs")
        protocol, fit = json.loads(protocol_bytes), json.loads(fit_bytes)
        receipt_bytes = normal.read("TARGET_NORMAL_06_RECEIPT.json")
        manifest = json.loads(normal.read("MANIFEST.json"))
        receipt = json.loads(receipt_bytes)
        check(sha256(receipt_bytes).hexdigest() == manifest["target_receipt_sha256"], "Stage 06 receipt differs")
        check(receipt["calibration"] == fit["calibration"] and (receipt["alarm_operator"], receipt["alarm_z"]) == (">", 3),
              "Frozen calibration differs")
        trace, blocks = (normal.read(name) for name in (TRACE, "TARGET_NORMAL_06_BLOCKS.csv"))
        for name, content in ((TRACE, trace), ("TARGET_NORMAL_06_BLOCKS.csv", blocks)):
            check(sha256(content).hexdigest() == receipt["artifacts"][name], f"Stage 06 {name} differs")
        historic = json.loads(design.read("HISTORICAL_FREEZE_RECEIPT.json"))
        train = source_audit(source, protocol)
        check(train["eligible_training_minutes"] == fit["train_minutes"], "Source train count differs")
        support = fit["train_support_degF"]
        check(all(support[name] == [train["features"]["summary_degF"][name][key] for key in ("min", "max")]
                  for name in FEATURES), "Source envelope differs")
        target = target_audit(trace, list(csv.DictReader(blocks.decode().splitlines())), receipt, support)
    data = {
        "decision": "ACCEPT_NEGATIVE_TRANSFER_RESULT", "candidate": protocol["candidate"],
        "source_calibration_domain": "LBNL_SIMULATED_SDAHU_2018",
        "training_setpoint_support": train["training_setpoint_support"], "setpoint_used_as_feature": False,
        "transfer_normal_gate": target["transfer_normal_gate"], "target_fault_eval_allowed": False,
        "external_field_validation": False, "deployment_eligible": False,
        "source_fit_versions": fit["versions"], "model_feature_order": fit["feature_order"],
        "frozen_alarm": {"operator": ">", "z": 3}, "source_calibration": fit["calibration"],
        "publisher": protocol["publisher"], "sha256": {
            "accepted_stage_05_zip": ARCHIVE_05, "accepted_stage_06_zip": ARCHIVE_06,
            "protocol": PROTOCOL_SHA, "source_fit_receipt": FIT_SHA,
            "target_normal_receipt": sha256(receipt_bytes).hexdigest(), "audit_script": sha(Path(__file__)),
            **receipt["sha256"], **receipt["artifacts"],
        },
        "source_training_audit": train, "saved_target_trace_audit": target,
        "historic_lbnl_within_source": historic["historical_primary"],
        "target_raw_opened": False, "model_loaded": False, "prediction_calls": 0,
    }
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print("PASS 70,842 frozen train minutes; 10,080 saved target rows; six mode 4 samples; STOP_OOD_HEALTHY preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "design_archive", "normal_archive", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
