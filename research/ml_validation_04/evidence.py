"""Recalculate archived results from pinned daily receipts. No inference or fitting."""
import argparse
from collections import defaultdict
import csv
from hashlib import file_digest
import json
from pathlib import Path

COHORT_SHA = "5adb2e3656e053aa29112ee86acfb06ce3ab81c49ddd802e6dca34640249786a"
HISTORICAL_SHA = "daf7069f16da8e1fcbf28e9825c198b4e47ede103ddce92d42cec905b1cf2648"
SAT = "sat_only"
SYSTEM = "system_max_8"
SETPOINT = "sat_minus_setpoint"
CONTROLS = ("ridge", "pca_paper", "pca_input_matched")
METHODS = (SAT, SYSTEM, SETPOINT, *CONTROLS)
BASE = "AHU_annual.csv"
PRIMARY = "coi_bias_2_annual.csv"
POLICY = "sat-daily-coverage@1.0.0"
TOLERANCE = 1e-9
THRESHOLD = 3


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def load_csv(path, expected=None):
    if expected and sha(path) != expected:
        raise ValueError(f"Evidence hash mismatch: {path.name}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def alarms(scores):
    return {day for day, value in scores.items() if value > THRESHOLD}


def metrics(normal, fault):
    tp, fp = len(alarms(fault)), len(alarms(normal))
    wins = sum((p > n) + (0.5 if p == n else 0) for n in normal.values() for p in fault.values())
    return {"tp": tp, "fp": fp, "fn": len(fault) - tp, "tn": len(normal) - fp,
            "auc": wins / (len(normal) * len(fault))}


def daily_scores(rows, method):
    return {day: float(row[f"{method}_policy_z"]) for day, row in rows.items() if row[f"{method}_policy_z"]}


def split_days(sat, system, prefix):
    if sat.keys() != system.keys() or any(system[day] + TOLERANCE < sat[day] for day in sat):
        raise ValueError("Invalid eight-target maximum or comparison calendar")
    left, right = alarms(sat), alarms(system)
    changed = {day for day in sat if abs(system[day] - sat[day]) > TOLERANCE}
    only_score = changed - (left ^ right)
    partitions = {
        "both": left & right, "system_only": right - left, "sat_only": left - right,
        "neither": sat.keys() - (left | right), "score_only": only_score,
    }
    summary = {}
    for label, values in partitions.items():
        summary[f"{prefix}_{label}_count"] = len(values)
        summary[f"{prefix}_{label}_days"] = "|".join(sorted(values))
    return summary


def matched_results(rows):
    groups = defaultdict(dict)
    for row in rows:
        if row["scope"] != "MATCHED_MINUTES":
            continue
        if row["policy"] != POLICY:
            raise ValueError("Unrecognized coverage policy")
        group = groups[row["pair_member"], row["member"]]
        if row["day"] in group:
            raise ValueError("Duplicate day")
        group[row["day"]] = row
    scenarios = sorted({pair for pair, _ in groups})
    if len(scenarios) != 11:
        raise ValueError("Expected eleven unique simulation scenarios")
    summary, primary = [], None
    for pair in scenarios:
        normal, fault = groups[pair, BASE], groups[pair, pair]
        if len(normal) != 73 or normal.keys() != fault.keys():
            raise ValueError("Incomplete paired calendar")
        for day in normal:
            left, right = normal[day], fault[day]
            if (left["usable_timestamps_sha256"], left["usable_minutes"]) != (
                    right["usable_timestamps_sha256"], right["usable_minutes"]):
                raise ValueError("Unequal paired minute mask")
        normal_scores, fault_scores = ({method: daily_scores(group, method) for method in METHODS}
                                       for group in (normal, fault))
        valid = set.intersection(*(set(scores[method]) for scores in (normal_scores, fault_scores)
                                   for method in (SAT, SYSTEM, SETPOINT)))
        if any(set(scores[method]) != valid for scores in (normal_scores, fault_scores)
               for method in (SAT, SYSTEM, SETPOINT)):
            raise ValueError("Unequal native coverage")
        n = len(valid)
        usable = sum(int(normal[day]["usable_minutes"]) for day in valid)
        alias = next(iter(fault.values()))["alias_status"]
        coverage = {"calendar_days": len(normal), "evaluated_days": n, "not_evaluated_days": len(normal) - n,
                    "evaluated_paired_minutes_per_side": usable, "calendar_minutes_per_side": 1440 * len(normal)}
        counts = {method: metrics(normal_scores[method], fault_scores[method]) for method in (SAT, SYSTEM, SETPOINT)}
        summary.append({
            "member": pair, "scenario": next(iter(fault.values()))["scenario"], "alias_status": alias,
            **coverage, **{f"{method}_{key}": value for method in (SAT, SYSTEM) for key, value in counts[method].items()},
            **split_days(fault_scores[SAT], fault_scores[SYSTEM], "fault"),
            **split_days(normal_scores[SAT], normal_scores[SYSTEM], "healthy"),
        })
        if pair == PRIMARY:
            available = {method: len(normal_scores[method].keys() & fault_scores[method].keys()) for method in CONTROLS}
            sat_days, setpoint_days = (alarms(fault_scores[method]) for method in (SAT, SETPOINT))
            primary = {"member": pair, "alias_status": alias, "policy": POLICY, "scope": "MATCHED_MINUTES",
                       **coverage, "metrics": counts, "ridge_pca_common_dates": available,
                       "sat_only_days_vs_setpoint": sorted(sat_days - setpoint_days),
                       "setpoint_only_days_vs_sat": sorted(setpoint_days - sat_days)}
    if primary is None:
        raise ValueError("Missing primary comparison")
    return summary, primary


def divergence(rows, historical):
    lookup = {(row["scenario"], row["day"], row["model"]): row for row in historical}
    fields = {SAT: ("LightGBM", "SA_TEMP"), SYSTEM: ("LightGBM", "z"), SETPOINT: ("SAT setpoint", "z"),
              "ridge": ("Ridge", "z"), "pca_paper": ("PCA-paper", "z"),
              "pca_input_matched": ("PCA-input-matched", "z")}
    all_delta = []
    checked = changed = 0
    for row in rows:
        if row["scope"] != "ORIGINAL_ARM_MASK":
            continue
        for method, (label, column) in fields.items():
            old = lookup.get((row["scenario"], row["day"], label), {}).get(column, "")
            new = row[f"{method}_z"]
            if bool(old) != bool(new):
                raise ValueError("Original-mask coverage divergence")
            if not old:
                continue
            old, new = float(old), float(new)
            checked += 1
            alarm_changed = (old > THRESHOLD) != (new > THRESHOLD)
            changed += alarm_changed
            if abs(old - new) > TOLERANCE or alarm_changed:
                all_delta.append({"member": row["member"], "scenario": row["scenario"], "day": row["day"],
                                  "method": method, "repro01_z": old, "repro03_z": new, "absolute_delta": abs(old - new),
                                  "alarm_changed": alarm_changed, "margin_from_threshold": min(abs(old - THRESHOLD), abs(new - THRESHOLD))})
    return all_delta, {"checked_alarm_flags": checked, "changed_alarm_flags": changed,
                       "divergent_rows": len(all_delta), "tolerance": TOLERANCE,
                       "max_absolute_delta": max(row["absolute_delta"] for row in all_delta)}


def main(cohort, historical, output):
    rows = load_csv(cohort, COHORT_SHA)
    baseline = load_csv(historical, HISTORICAL_SHA)
    summaries, primary = matched_results(rows)
    deltas, parity = divergence(rows, baseline)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "SAT_VS_SYSTEM_11_SCENARIOS.csv", summaries)
    write_csv(output / "ALARM_PARITY_DIVERGENCE.csv", deltas)
    receipt = {"cohort_sha256": COHORT_SHA, "historical_sha256": HISTORICAL_SHA, "threshold": THRESHOLD,
               "primary": primary, "alarm_parity": parity}
    (output / "RECALCULATION.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(f"Verified {len(summaries)} scenario comparisons and {parity['checked_alarm_flags']} historical alarm flags")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cohort", "historical", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
