"""Stage13 offline preparation and per-episode descriptive calculation."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from statistics import linear_regression, median

from research.ml_field_observational_12 import replay as base

PREFIX = "FIELD_REPLICATION_13_PREREG"
PIN = {".md": "da69ec2ae6f7da73d4485320846d4fbb3a3f9c600a4c7bcb679150a0965d7378",
       ".json": "00669603c6ee682b260ba888fdd6ef4dcc7deb1530148d2abe2ceb3303704558"}
LIMITS = ["CAUSAL_EFFECT_NOT_IDENTIFIED", "FIELD_FDD_ACCURACY_NOT_EVALUATED",
          "SAME_SITE_TWO_DATES", "NOT_INDEPENDENT_BUILDING_VALIDATION"]
LEDGER = "EPISODE_LEDGER_13.csv"
CANDIDATES = "COMPARATOR_ELIGIBILITY_13.csv"
SELECTION = "SELECTION_13.json"
TRACE = "RAW_SLICE_13.csv"
ANN = "PUBLISHER_ANNOTATIONS_13.csv"
AUDIT = "ANNOTATION_AUDIT_13.csv"
FEAS = "FEASIBILITY_13.csv"
FILES = (LEDGER, CANDIDATES, SELECTION, TRACE, ANN, AUDIT, FEAS)
META = ["Time", "site", "ahu", "schedule_row", "window_id", "kind", "partition"]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def protocol_from(folder):
    for suffix, digest in PIN.items():
        if base.digest(folder / (PREFIX + suffix)) != digest:
            raise base.Stop("STOP_SOURCE_PREREG_SHA")
    created = datetime.fromisoformat((folder / (PREFIX + "_CREATED_AT.txt")).read_text().strip())
    if created.tzinfo is None or created >= datetime.now(base.TZ):
        raise base.Stop("STOP_SOURCE_PREREG_CLOCK")
    return json.loads((folder / (PREFIX + ".json")).read_text())


def event_protocol(protocol, event):
    bounds = (event.start - timedelta(minutes=protocol["pre_minutes"]), event.start, event.end,
              event.end + timedelta(minutes=protocol["post_minutes"]))
    return {**protocol, "ahu": event.ahu, "schedule_row": event.row, "event_date": str(event.day),
            "boundaries": [stamp.strftime("%H:%M") for stamp in bounds]}


def choose_comparison(days):
    ordered = sorted(days, key=lambda day: (abs(day["relative_weeks"]), day["date"]))
    match = next((day for day in ordered if day["eligible"]), None)
    return ordered, match["date"] if match else None


def rows_for_episode(raw, config, event, windows):
    temperatures, commands, status = base.signal_columns(config)
    columns = (*temperatures, *commands, status)
    expected = {}
    for day, label in windows.items():
        for partition, timestamps in base.expected_ticks(date.fromisoformat(day), config).items():
            expected.update({stamp: (label, partition) for stamp in timestamps})
    rows, annotations = [], []
    for stamp, *values in base.telemetry(raw, config, (*columns, "fault")):
        if stamp not in expected:
            continue
        label, partition = expected[stamp]
        metadata = {"Time": str(stamp), "site": base.SITE, "ahu": event.ahu, "schedule_row": event.row,
                    "window_id": f"row{event.row}_{label}", "kind": label, "partition": partition}
        rows.append({**metadata, **{key: val if base.finite(val) else None for key, val in zip(columns, values[:-1])}})
        annotations.append({**metadata, "publisher_fault_evaluation_only": values[-1]})
    if len(rows) != len(expected):
        raise base.Stop(f"STOP_SOURCE_EXTRACTION_GRID row{event.row}")
    return rows, annotations


def seal(output):
    (output / "PREPARED_13.sha256").write_text(
        "".join(f"{base.digest(output / name)}  {name}\n" for name in FILES))


def prepare(raw, output, protocol, manifest):
    temperatures, commands, status = base.signal_columns(protocol)
    columns = (*temperatures, *commands, status)
    schedule = base.read_schedule(raw)
    event_by_row = {event.row: event for event in schedule}
    source_masks = {}
    ledger, candidates, configs = [], [], {}
    selected = {}
    for row, number, ahu, day, duration in protocol["episodes"]:
        event = event_by_row.get(row)
        if (event is None or (event.fault, event.ahu, str(event.day)) != (f"Fault {number}", ahu, day)
                or event.start is None or (event.end - event.start).total_seconds() != duration * 60
                or any(stamp.minute % 5 or stamp.second or stamp.microsecond for stamp in (event.start, event.end))):
            raise base.Stop(f"STOP_SOURCE_SCHEDULE_MISMATCH row{row}")
        cfg = configs[row] = event_protocol(protocol, event)
        if ahu not in source_masks:
            source_masks[ahu] = base.read_masks(raw, cfg)
        first, last, masks = source_masks[ahu]
        decision = base.qualify(event.day, cfg, schedule, masks, primary=True)
        comparator = None
        examined = eligible = 0
        if decision["eligible"]:
            days = (first.date() + timedelta(days=i) for i in range((last.date() - first.date()).days + 1))
            cohort = [base.qualify(other, cfg, schedule, masks) for other in days
                      if other.weekday() == event.day.weekday() and other != event.day]
            ordered, comparator = choose_comparison(cohort)
            examined, eligible = len(cohort), sum(row["eligible"] for row in cohort)
            candidates.extend({"schedule_row": row, "ahu": ahu, **item,
                               "selected": item["date"] == comparator} for item in ordered)
            selected[row] = {day: "event", **({comparator: "comparison"} if comparator else {})}
        ledger.append({
            "schedule_row": row, "fault": event.fault, "ahu": ahu, "duration_minutes": duration,
            "cohort": "main_120m" if duration == 120 else "short_30m",
            "start_native": str(event.start), "end_exclusive_native": str(event.end), "clock": protocol["clock"],
            **decision, "analysis_status": "QUALIFIED" if decision["eligible"] else "NOT_EVALUABLE",
            "comparison_status": ("MATCHED_UNVERIFIED_HEALTH" if comparator else "NO_MATCHED_CONTROLS")
            if decision["eligible"] else "NOT_EVALUABLE",
            "comparison_date": comparator, "comparison_dates_screened": examined, "comparison_dates_eligible": eligible,
            "source_sha256": manifest["files"][ahu + ".xlsx"]["publisher_sha256"],
        })
    for row, reason in protocol["excluded"]:
        event = event_by_row.get(row)
        if event is None or event.start is None:
            raise base.Stop(f"STOP_SOURCE_SCHEDULE_MISMATCH row{row}")
        ledger.append({
            "schedule_row": row, "fault": event.fault, "ahu": event.ahu, "date": str(event.day),
            "duration_minutes": (event.end - event.start) // timedelta(minutes=1),
            "cohort": "excluded", "start_native": str(event.start), "end_exclusive_native": str(event.end),
            "clock": protocol["clock"], "eligible": False, "reasons": reason, "analysis_status": "NOT_EVALUABLE"
            if reason == "MISSING_CHANNELS" else "PREVIOUSLY_EXPLORED", "comparison_status": "NOT_SCREENED",
            "source_sha256": manifest["files"][event.ahu + ".xlsx"]["publisher_sha256"],
        })
    base.table(output / LEDGER, sorted(ledger, key=lambda item: item["schedule_row"]), list(ledger[0]))
    candidate_fields = ["schedule_row", "ahu", *[key for key in decision], "selected"]
    base.table(output / CANDIDATES, candidates, candidate_fields)
    base.dump(output / SELECTION, {
        "selection_sealed_at": datetime.now(base.TZ).isoformat(), "site": base.SITE,
        "selected": selected, "selection_input": "native clock + finite SAT flag + BAS context + schedule bounds",
        "limits": LIMITS,
    })
    print("SELECTION SEALED", selected, "no medians computed", flush=True)
    rows, annotations, checks = [], [], []
    annotation_audit = []
    for row, windows in selected.items():
        event, cfg = event_by_row[row], configs[row]
        trace, labels = rows_for_episode(raw, cfg, event, windows)
        rows.extend(trace)
        annotations.extend(labels)
        sha = manifest["files"][event.ahu + ".xlsx"]["publisher_sha256"]
        checks.extend(base.feasibility(trace, cfg, sha))
        own_labels = {event.fault.casefold(), event.title.casefold()}
        grouped = defaultdict(Counter)
        for ann in labels:
            grouped[ann["window_id"], ann["partition"]][str(ann["publisher_fault_evaluation_only"] or "")] += 1
        for (window, part), counts in grouped.items():
            annotation_audit.append({
                "window_id": window, "partition": part,
                "matching_episode_label_ticks": sum(n for label, n in counts.items()
                                                    if label.strip().casefold() in own_labels),
                "label_histogram_evaluation_only": json.dumps(dict(counts), sort_keys=True),
            })
    base.table(output / TRACE, rows, [*META, *columns])
    base.table(output / ANN, annotations, [*META, "publisher_fault_evaluation_only"])
    base.table(output / AUDIT, annotation_audit,
               ["window_id", "partition", "matching_episode_label_ticks", "label_histogram_evaluation_only"])
    base.table(output / FEAS, checks, list(checks[0]) if checks else
               ["window_id", "partition", "native_header", "unit", "role", "native_ticks", "finite",
                "missing", "min", "max", "adjacent_command_or_status_changes", "source_sha256"])
    seal(output)
    print(f"PREPARED {len(rows)} rows; masks, ranges and roles recorded before calculation", flush=True)


def decision_from(sat_rows):
    main = [row for row in sat_rows if row["kind"] == "event" and row["cohort"] == "main_120m"]
    units = {fault: sorted({row["ahu"] for row in main if row["fault"] == fault})
             for fault in ("Fault 4", "Fault 6")}
    signs = sorted({row["sign"] for row in main})
    if any(len(group) < 2 for group in units.values()):
        decision = "STOP_INSUFFICIENT_NATIVE_DATA"
    elif len(signs) > 1:
        decision = "HETEROGENEOUS_OBSERVATIONS"
    else:
        decision = "DESCRIPTIVE_MULTI_AHU_OBSERVED"
    return decision, units, signs


def calculate(output, protocol):
    expected = "".join(f"{base.digest(output / name)}  {name}\n" for name in FILES)
    if (output / "PREPARED_13.sha256").read_text() != expected:
        raise base.Stop("STOP_SOURCE_PREPARATION_SHA")
    ledger = {row["schedule_row"]: row for row in read_csv(output / LEDGER)}
    data = defaultdict(list)
    for row in read_csv(output / TRACE):
        data[row["window_id"], row["partition"]].append(row)
    sat_rows, summaries = [], []
    for window in dict.fromkeys(key[0] for key in data):
        rownum = window.split("_")[0].removeprefix("row")
        event = ledger[rownum]
        kind = window.split("_")[1]
        phases = {part: data[window, part] for part in base.PARTS}
        for field in (protocol["sat"], *protocol["secondary"]):
            values = {part: [float(r[field]) for r in samples if r[field]]
                      for part, samples in phases.items()}
            med = {part: median(series) if series else None for part, series in values.items()}
            delta = med["WINDOW"] - med["PRE"] if med["WINDOW"] is not None and med["PRE"] is not None else None
            slopes = {}
            if field == protocol["sat"]:
                for part, points in phases.items():
                    first = datetime.fromisoformat(points[0]["Time"])
                    hours = [(datetime.fromisoformat(r["Time"]) - first).total_seconds() / 3600 for r in points]
                    slopes[part] = linear_regression(hours, values[part]).slope
            summary = {
                "window_id": window, "kind": kind, "schedule_row": int(rownum), "ahu": event["ahu"],
                "fault": event["fault"], "cohort": event["cohort"], "duration_minutes": int(event["duration_minutes"]),
                "date": phases["WINDOW"][0]["Time"][:10], "channel": field, "unit": "°C",
                **{part + "_finite": len(series) for part, series in values.items()},
                **{part + "_median": med[part] for part in base.PARTS},
                **{part + "_SAT_OLS_C_per_hour": slopes.get(part) for part in base.PARTS},
                "window_minus_pre_C": delta, "sign": (None if delta is None else
                                                     "negative" if delta < 0 else "positive" if delta > 0 else "zero"),
            }
            summaries.append(summary)
            if field == protocol["sat"]:
                sat_rows.append(summary)
    fields = ["window_id", "kind", "schedule_row", "ahu", "fault", "cohort", "duration_minutes", "date",
              "channel", "unit", *[p + suffix for suffix in ("_finite", "_median", "_SAT_OLS_C_per_hour")
                                   for p in base.PARTS], "window_minus_pre_C", "sign"]
    base.table(output / "DESCRIPTIVE_EPISODES_13.csv", summaries, fields)
    decision, units, signs = decision_from(sat_rows)
    base.dump(output / "RESULT_13.json", {
        "status": decision, "limits": LIMITS, "stage11_causal_gate": "STOP", "site_count": 1,
        "registered_main_dates": sorted({item[3] for item in protocol["episodes"] if item[4] == 120}),
        "qualified_main_ahu_by_fault": units, "main_signs": signs,
        "matched_comparisons": sum(r["kind"] == "comparison" for r in sat_rows),
        "sat_results": sat_rows, "calculated_at": datetime.now(base.TZ).isoformat(),
    })
    print(decision, units, signs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "calculate"))
    parser.add_argument("raw", type=Path)
    parser.add_argument("protocol_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        config = protocol_from(args.protocol_dir)
        manifest = base.verify_sources(args.raw, args.protocol_dir, config)
        if args.step == "prepare":
            prepare(args.raw, args.output, config, manifest)
        else:
            calculate(args.output, config)
    except (base.Stop, OSError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
