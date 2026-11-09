"""Independent standard-library replay of masks and statistics, with zero model calls."""
import argparse
from collections import Counter
import csv
import gzip
from hashlib import file_digest
from itertools import groupby
import json
import math
from pathlib import Path

START, STEP, WIDTH, DAYS = 17625600, 60, 1440, 7
FIT_SHA = "1187a8aa96ff7c64ef4e4c0613bee91e8acf5d3bbc794c7d314889ee451fff84"
RIDGE_SHA = "a0e122b112ad2ae6b914635bf161d8977b5a11283b75260b620504dfd317f7de"
FEATURES = ("MA_TEMP", "OA_TEMP", "RA_TEMP")
SAT = "SAT_MEASURED_SIMULATED_BAS_degF"
SP = "ACTIVE_SAT_SETPOINT_degF"
METHODS = {
    "lightgbm_reduced": ("LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF", "LIGHTGBM_ABS_RESIDUAL_degF"),
    "ridge_reduced": ("RIDGE_SOURCE_TRAINED_PREDICTION_degF", "RIDGE_ABS_RESIDUAL_degF"),
    "sat_minus_sp": (SP, "SAT_MINUS_SETPOINT_ABS_RESIDUAL_degF"),
}
TOLERANCE = 1e-10


def check(condition, description):
    if not condition:
        raise ValueError(description)


def digest(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def numeric(row, key):
    value = row[key]
    return float(value) if value else None


def near(observed, expected, field):
    value = float(observed) if observed is not None and observed != "" else None
    check(value is expected if expected is None or value is None else
          math.isclose(value, expected, abs_tol=TOLERANCE, rel_tol=0), f"Difference in {field}")


def mean(values):
    return math.fsum(values) / len(values) if values else None


def longest(flags):
    return max((sum(1 for _ in items) for state, items in groupby(flags) if state), default=0)


def stats(values):
    return {"min": min(values), "mean": mean(values), "max": max(values)} if values else None


def main(directory, artifacts, output):
    fit_path = artifacts / "SOURCE_FIT_RECEIPT.json"
    ridge_path = artifacts / "REDUCED_SAT_RIDGE.json"
    check(digest(fit_path) == FIT_SHA and digest(ridge_path) == RIDGE_SHA, "Frozen fit or Ridge SHA differs")
    fit, ridge = json.loads(fit_path.read_text()), json.loads(ridge_path.read_text())
    check(tuple(ridge["feature_order"]) == FEATURES, "Ridge feature order differs")
    receipt = json.loads((directory / "TARGET_NORMAL_06_RECEIPT.json").read_text())
    check(receipt["calibration"] == fit["calibration"] and receipt["source_support_degF"] == fit["train_support_degF"]
          and (receipt["alarm_operator"], receipt["alarm_z"]) == (">", 3), "Decision settings changed")
    limits = fit["train_support_degF"]
    check(receipt["fault_phase_authorized"] is False and receipt["target_fault_prediction_executed"] is False,
          "Fault evaluation boundary changed")
    for name, expected in receipt["artifacts"].items():
        check(digest(directory / name) == expected, "Output SHA differs")
    with gzip.open(directory / "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz", "rt", newline="") as stream:
        minutes = list(csv.DictReader(stream))
    with (directory / "TARGET_NORMAL_06_BLOCKS.csv").open(newline="") as stream:
        blocks = list(csv.DictReader(stream))
    check(len(minutes) == WIDTH * DAYS and len(blocks) == DAYS, "Unexpected block shape")

    streak = 0
    tech = False
    candidate, running_warm = [], []
    for index, row in enumerate(minutes):
        check(int(row["model_seconds"]) == START + STEP * index and int(row["block"]) == index // WIDTH
              and int(row["csv_row_1based"]) == index + 2, "Wrong time/row at " + str(index))
        fan, oat, mode = (numeric(row, name) for name in ("FAN_STATUS", "OA_TEMP_degF", "PLANT_MODE"))
        streak = streak + 1 if fan == 1 else 0
        running, warm = streak >= 6, oat is not None and oat > 60
        x = [numeric(row, feature + "_degF") for feature in FEATURES]
        support = all(value is not None and limits[name][0] <= value <= limits[name][1]
                      for name, value in zip(FEATURES, x, strict=True))
        valid_mode = mode in (1, 2, 3, 4)
        bad_units = row["INVALID_UNIT_OR_RANGE"] == "True"
        eligible = (running and warm and support and valid_mode and not bad_units
                    and numeric(row, SAT) is not None and numeric(row, SP) is not None)
        tech |= fan not in (0, 1) or oat is None or not valid_mode or bad_units
        check(all(row[name] == str(value) for name, value in (
            ("RUNNING", running), ("WARM", warm), ("RUNNING_WARM", running and warm),
            ("SOURCE_SUPPORT", support), ("MINUTE_ELIGIBLE", eligible))), "Trace mask differs at " + str(index))
        candidate.append(eligible)
        running_warm.append(running and warm)

    used_rows, block_results = [], []
    residuals = {method: [] for method in METHODS}
    signed = {method: [] for method in METHODS}
    for block, supplied in enumerate(blocks):
        start, end = block * WIDTH, (block + 1) * WIDTH
        segment = minutes[start:end]
        raw, denominator = candidate[start:end], sum(running_warm[start:end])
        run = longest(raw)
        valid = not tech and sum(raw) >= 120 and run >= 30 and denominator > 0 and sum(raw) / denominator >= 0.8
        use = [row for row, eligible in zip(segment, raw, strict=True) if eligible and valid]
        used_rows.extend(use)
        check(supplied["status"] == ("EVALUATED" if valid else "ABSTAIN"), "Block decision mismatch")
        mode_counts = Counter(numeric(row, "PLANT_MODE") for row in segment)
        mode_used = Counter(numeric(row, "PLANT_MODE") for row in use)
        for key, expected in {
            "block": block, "start_model_s": START + STEP * start, "end_exclusive_model_s": START + STEP * end,
            "calendar_minutes": WIDTH, "warm_running_minutes": denominator,
            "eligible_before_block_gate": sum(raw), "eligible_minutes": len(use),
            "max_contiguous_candidate_minutes": run, "max_contiguous_scored_minutes": run if valid else 0,
            "fan_missing": sum(not row["FAN_STATUS"] for row in segment),
            "oat_missing": sum(not row["OA_TEMP_degF"] for row in segment),
            "plant_mode_missing": mode_counts[None],
            "invalid_unit_or_range": sum(row["INVALID_UNIT_OR_RANGE"] == "True" for row in segment),
            "warm_running_outside_support": sum(row["RUNNING_WARM"] == "True" and row["SOURCE_SUPPORT"] == "False"
                                                for row in segment),
            **{f"mode_{i}_{suffix}": counts[i] for i in (1, 2, 3, 4)
               for suffix, counts in (("minutes", mode_counts), ("eligible", mode_used))},
        }.items():
            check(int(supplied[key]) == expected, f"Block {block}: {key}")
        near(supplied["coverage"], len(use) / denominator if denominator else None, "coverage")
        near(supplied["calendar_coverage"], len(use) / WIDTH, "calendar coverage")
        for tick, selected in zip(segment, raw, strict=True):
            selected = selected and valid
            check(tick["ELIGIBLE"] == str(selected), "Shared score mask differs")
            check(bool(tick["ABSTAIN_REASON"]) != selected, "Missing or spurious abstention reason")
            if not selected:
                check(all(not tick[residual] for _, residual in METHODS.values())
                      and not tick[METHODS["lightgbm_reduced"][0]] and not tick[METHODS["ridge_reduced"][0]],
                      "Prediction or residual on an excluded tick")
        metrics = {}
        for method, (prediction, residual) in METHODS.items():
            daily = []
            for row in use:
                actual, predicted = numeric(row, SAT), numeric(row, prediction)
                check(predicted is not None and math.isfinite(predicted), "Prediction missing on shared mask")
                if method == "ridge_reduced":
                    calculated = ridge["intercept"] + math.fsum(
                        (numeric(row, name + "_degF") - center) / scale * coef
                        for name, center, scale, coef in zip(FEATURES, ridge["mean"], ridge["scale"],
                                                            ridge["coefficient"], strict=True)
                    )
                    near(predicted, calculated, "Ridge formula")
                error = actual - predicted
                daily.append(abs(error))
                signed[method].append(error)
                near(row[residual], abs(error), residual)
            residuals[method].extend(daily)
            mae = mean(daily)
            params = fit["calibration"][method]
            z = (mae - params["center"]) / params["scale"] if daily else None
            decision = "ABSTAIN" if z is None else "ALERT" if z > 3 else "NO_ALERT"
            near(supplied[method + "_mae_degF"], mae, "MAE")
            near(supplied[method + "_z"], z, "z")
            check(supplied[method + "_decision"] == decision, "Threshold decision mismatch")
            metrics[method] = {"mae_degF": mae, "z": z, "decision": decision}
        block_results.append({"block": block, "evaluated": valid, "methods": metrics})

    evaluated = sum(row["evaluated"] for row in block_results)
    counts = {method: [row["block"] for row in block_results if row["methods"][method]["decision"] == "ALERT"]
              for method in METHODS}
    eligible_count, total = len(used_rows), sum(running_warm)
    failures = [reason for failed, reason in (
        (tech, "TECHNICAL_INPUT_OBSERVABILITY"), (evaluated < 3, "TOO_FEW_EVALUATED_BLOCKS"),
        (not total or eligible_count / total < 0.8, "INSUFFICIENT_WINDOW_COVERAGE"),
        (bool(counts["lightgbm_reduced"]), "LIGHTGBM_NORMAL_ALARM"),
    ) if failed]
    gate = "STOP_OOD_HEALTHY" if failures else "PASS_TARGET_NORMAL_AWAITING_FAULT_APPROVAL"
    check(receipt["gate"] == gate and receipt["gate_failed_conditions"] == failures, "Gate outcome differs")
    check((receipt["eligible_minutes"], receipt["warm_running_minutes"], receipt["evaluated_blocks"]) ==
          (eligible_count, total, evaluated), "Window denominators differ")
    for method in METHODS:
        measured = receipt["methods"][method]
        check(measured["alarm_blocks"] == counts[method], "Window alarm count differs")
        near(measured["pooled_mae_degF"], mean(residuals[method]), "Window MAE")
        near(measured["false_alarm_rate_conditional"], len(counts[method]) / evaluated if evaluated else None, "Window FAR")
        for observed, row in zip(measured["daily_z"], block_results, strict=True):
            near(observed, row["methods"][method]["z"], "Window daily z")
    mode_summary = {}
    for i in (1, 2, 3, 4):
        selected = [row for row in used_rows if numeric(row, "PLANT_MODE") == i]
        calendar = sum(numeric(row, "PLANT_MODE") == i for row in minutes)
        warm_running = sum(warm and numeric(row, "PLANT_MODE") == i for row, warm in zip(minutes, running_warm, strict=True))
        check((receipt[f"mode_{i}_minutes"], receipt[f"mode_{i}_eligible"]) == (calendar, len(selected)), "Window mode counts differ")
        mode_summary[str(i)] = {"calendar_minutes": calendar, "warm_running_minutes": warm_running,
                                "eligible_minutes": len(selected), "pooled_mae_degF": {
            name: mean([numeric(row, residual) for row in selected]) for name, (_, residual) in METHODS.items()
        }}
    with output.open("x") as stream:
        json.dump({
            "status": "PASS_TRACE_RECONCILIATION", "model_calls": 0, "gate": gate, "gate_failed_conditions": failures,
            "rows": len(minutes), "eligible_minutes": eligible_count, "evaluated_blocks": evaluated,
            "alarm_blocks": counts, "blocks": block_results, "mode_summary": mode_summary,
            "eligible_input_ranges_degF": {name: stats([numeric(row, name + "_degF") for row in used_rows]) for name in FEATURES},
            "eligible_measured_sat_degF": stats([numeric(row, SAT) for row in used_rows]),
            "eligible_active_setpoint_degF": stats([numeric(row, SP) for row in used_rows]),
            "eligible_lightgbm_prediction_degF": stats([numeric(row, METHODS["lightgbm_reduced"][0]) for row in used_rows]),
            "eligible_ridge_prediction_degF": stats([numeric(row, METHODS["ridge_reduced"][0]) for row in used_rows]),
            "pooled_signed_actual_minus_prediction_degF": {name: mean(values) for name, values in signed.items()},
            "tolerance": TOLERANCE,
        }, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"PASS {len(minutes)} trace rows; exact shared mask, Ridge arithmetic, 7 blocks and gate reproduced")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("directory", "artifacts", "output"):
        parser.add_argument(arg, type=Path)
    main(**vars(parser.parse_args()))
