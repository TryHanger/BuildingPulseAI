"""Independently compare exported daily scores using only the standard library."""
import argparse
from collections import defaultdict
import csv
from datetime import date, timedelta
from hashlib import file_digest
from itertools import combinations
import json
from math import isfinite
from pathlib import Path

METHODS = ("sat_only", "system_max_8", "sat_minus_setpoint", "ridge", "pca_paper", "pca_input_matched")
BASELINE = "AHU_annual.csv"
TOLERANCE = 1e-9
LEGACY = {
    "sat_only": ("LightGBM", "SA_TEMP"),
    "system_max_8": ("LightGBM", "z"),
    "sat_minus_setpoint": ("SAT setpoint", "z"),
    "ridge": ("Ridge", "z"),
    "pca_paper": ("PCA-paper", "z"),
    "pca_input_matched": ("PCA-input-matched", "z"),
}
DAILY_PINS = {
    "PRODUCT_BASIC": "daf7069f16da8e1fcbf28e9825c198b4e47ede103ddce92d42cec905b1cf2648",
    "PRODUCT_BASIC_WITHOUT_COMMANDS": "139c30e026628b3c20046b4628382d3d710c0fdee95e8fa2aac132c506163e0b",
}


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def metrics(healthy, fault):
    h_days = set(day for day, z in healthy.items() if z > 3)
    f_days = set(day for day, z in fault.items() if z > 3)
    negative, positive = list(healthy.values()), list(fault.values())
    wins = sum(1 if p > n else 0.5 if p == n else 0 for n in negative for p in positive)
    n = len(negative) * len(positive)
    return {"tp": len(f_days), "fp": len(h_days), "fn": len(fault) - len(f_days), "tn": len(healthy) - len(h_days),
            "auc": wins / n if n else None, "fault_alarm_days": days(f_days), "healthy_alarm_days": days(h_days),
            "fault_non_alarm_days": days(fault.keys() - f_days), "healthy_non_alarm_days": days(healthy.keys() - h_days)}


def days(items):
    return "|".join(sorted(items))


def pairwise(negative, positive, context, suffix, names):
    for left, right in combinations(names, 2):
        valid = sorted(day for day in negative.keys() & positive.keys()
                       if all(negative[day].get(method + suffix) and positive[day].get(method + suffix)
                              for method in (left, right)))
        ha, hb = [{day: float(negative[day][method + suffix]) for day in valid} for method in (left, right)]
        fa, fb = [{day: float(positive[day][method + suffix]) for day in valid} for method in (left, right)]
        ah, bh, af, bf = [set(day for day, z in series.items() if z > 3) for series in (ha, hb, fa, fb)]
        stats = {side + "_" + key: value for side, normal, fault in (("left", ha, fa), ("right", hb, fb))
                 for key, value in metrics(normal, fault).items()}
        yield {**context, "left": left, "right": right, "paired_days": len(valid),
               "calendar_days": len(positive), "excluded_days": days(positive.keys() - set(valid)),
               "paired_healthy_minutes": sum(int(negative[day]["usable_minutes"]) for day in valid),
               "paired_fault_minutes": sum(int(positive[day]["usable_minutes"]) for day in valid),
               "both_fault_alarm_days": days(af & bf), "left_only_fault_alarm_days": days(af - bf),
               "right_only_fault_alarm_days": days(bf - af), "neither_fault_alarm_days": days(set(valid) - af - bf),
               "both_healthy_alarm_days": days(ah & bh), "left_only_healthy_alarm_days": days(ah - bh),
               "right_only_healthy_alarm_days": days(bh - ah), "neither_healthy_alarm_days": days(set(valid) - ah - bh),
               **stats}


def legacy(directory, destination):
    evidence = []
    for arm, pin in DAILY_PINS.items():
        source = directory / arm / "daily.csv"
        if sha(source) != pin:
            raise ValueError(f"Historical daily CSV SHA mismatch: {arm}")
        grouped = defaultdict(lambda: defaultdict(dict))
        for row in read(source):
            for method, (label, field) in LEGACY.items():
                if row["model"] == label and row[field] and isfinite(float(row[field])):
                    grouped[row["scenario"]][row["day"]][method + "_z"] = row[field]
                    grouped[row["scenario"]][row["day"]]["usable_minutes"] = row["ticks"]
        for scenario, fault in grouped.items():
            if scenario == "healthy":
                continue
            evidence.extend(pairwise(grouped["healthy"], fault, {
                "evidence": "REPRO_01_SAVED_DAILY_CSV", "arm": arm, "scenario": scenario, "daily_sha256": pin,
            }, "_z", METHODS))
    write(destination, evidence)


def compare(cohort, metadata, legacy_directory, output):
    meta = json.loads(metadata.read_text())
    if sha(cohort) != meta["csv_sha256"]:
        raise ValueError("Full cohort CSV hash mismatch")
    original = legacy_directory / "PRODUCT_BASIC" / "daily.csv"
    if sha(original) != meta["legacy_daily_sha256"] or sha(original) != DAILY_PINS["PRODUCT_BASIC"]:
        raise ValueError("Historical BASIC daily CSV hash mismatch")
    saved = {(row["scenario"], row["day"], row["model"]): row for row in read(original)}
    source_rows = read(cohort)
    if len(source_rows) != meta["rows"]:
        raise ValueError("Full cohort row count mismatch")
    groups = defaultdict(dict)
    divergences = []
    maximum = defaultdict(float)
    for row in source_rows:
        key = (row["scope"], row["pair_member"], row["member"])
        day = row["day"]
        if day in groups[key]:
            raise ValueError(f"Duplicate cohort row: {key} {day}")
        groups[key][day] = row
        if row["source_sha256"] != meta["source_sha256"] or row["member_sha256"] != meta["source_members"][row["member"]]:
            raise ValueError("Source receipt mismatch")
        for method in METHODS:
            old, current = row[f"{method}_repro01_z"], row[f"{method}_z"]
            original_method, column = LEGACY[method]
            saved_row = saved.get((row["scenario"], day, original_method))
            mask_equal = row["historical_comparators_mask_equal"] == "True"
            expected_old = saved_row[column] if saved_row and mask_equal else ""
            if (float(old) if old else None) != (float(expected_old) if expected_old else None):
                raise ValueError(f"Historical score mismatch: {key} {day} {method}")
            if saved_row and mask_equal and saved_row["ticks"] != row["usable_minutes"]:
                raise ValueError(f"Historical comparator coverage mismatch: {key} {day} {method}")
            policy_score = row[f"{method}_policy_z"]
            if policy_score != (current if row["policy_status"] == "EVALUATED" else ""):
                raise ValueError(f"Coverage policy result mismatch: {key} {day} {method}")
            for score, alarm_field in ((current, "historical_alarm"), (policy_score, "policy_alarm")):
                expected = str(float(score) > 3) if score else ""
                if row[f"{method}_{alarm_field}"] != expected:
                    raise ValueError(f"Alarm mismatch: {key} {day} {method}")
            if row["scope"] != "ORIGINAL_ARM_MASK" or not old or not current:
                continue
            delta = abs(float(old) - float(current))
            maximum[method] = max(maximum[method], delta)
            alarm_change = (float(old) > 3) != (float(current) > 3)
            if delta > TOLERANCE or alarm_change:
                divergences.append({"member": row["member"], "day": day, "method": method,
                                    "repro01_z": old, "replay_z": current, "abs_delta": delta,
                                    "alarm_changed": alarm_change})
    first = date.fromisoformat(meta["split"]["test_start"].split()[0])
    calendar = {(first + timedelta(days=offset)).isoformat() for offset in range(meta["calendar_days"])}
    if any(group.keys() != calendar for group in groups.values()):
        raise ValueError("Incomplete calendar group")
    summary = []
    for (scope, pair, member), positive in groups.items():
        if member == BASELINE:
            continue
        negative = groups[scope, pair, BASELINE]
        if scope == "MATCHED_MINUTES" and any(
                positive[d]["usable_timestamps_sha256"] != negative[d]["usable_timestamps_sha256"] for d in positive):
            raise ValueError("Matched timestamps differ")
        for suffix, policy in (("_z", "REPRO_01_ANY_ELIGIBLE_MINUTE"), ("_policy_z", meta["policy_version"])):
            summary.extend(pairwise(negative, positive, {"scope": scope, "policy": policy, "member": member,
                "scenario": next(iter(positive.values()))["scenario"], "source_sha256": meta["source_sha256"],
                "member_sha256": meta["source_members"][member]}, suffix, METHODS))
    output.mkdir(parents=True, exist_ok=False)
    write(output / "PAIRED_METHOD_METRICS.csv", summary)
    legacy(legacy_directory, output / "REPRO01_SAVED_DAILY_METRICS.csv")
    if divergences:
        write(output / "DIVERGENCE.csv", divergences)
    else:
        (output / "DIVERGENCE.csv").write_text("member,day,method,repro01_z,replay_z,abs_delta,alarm_changed\n")
    (output / "PARITY_CHECK.json").write_text(json.dumps({
        "csv_sha256": meta["csv_sha256"], "absolute_tolerance": TOLERANCE,
        "maximum_absolute_deltas": maximum, "divergent_day_method_rows": len(divergences),
        "alarm_changes": sum(row["alarm_changed"] for row in divergences),
    }, indent=2) + "\n")
    print(f"Verified {len(source_rows)} rows, {len(summary)} pairwise metrics, "
          f"{len(divergences)} score divergences at tolerance {TOLERANCE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cohort", "metadata", "legacy_directory", "output"):
        parser.add_argument(name, type=Path)
    compare(**vars(parser.parse_args()))
