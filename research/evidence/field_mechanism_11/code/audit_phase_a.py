"""Stage11 source qualification only. No response or comparator is computed."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, time, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from openpyxl import load_workbook


AHUS = ("AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24")
SITE = "CTU-UCEEB_Bustehrad"
CLOCK = "UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S"
PERIOD = 300
SCHEDULE = "Faults_schedule_and_description.xlsx"
PDF = "CTU_AAM_350037.verified.pdf"
PDF_SHA = "4a03914e8064ae3b42ffce9a806a724f7451bae7596d940ff3884b6c50a072ef"
FREEZE = {
    "PREREGISTERED_11.md": "68789e86b735def4ee4c2a0034522f61a78a52b038f8873a3b78ac55780ae2b4",
    "PREREGISTERED_11.json": "697d78ca2f6e01234a18fd6024a0d95c6342dfb624762ed52609a51167738193",
}

# Keys are literal workbook headers. The source diagram provides place semantics,
# but supplies no equipment-specific point address or override allowlist.
POINTS = {
    "air_temperature__real_value__exahust_air_inlet":
        ("°C", "extract inlet from occupied space before heat recovery", "CANDIDATE_PROCESS_SENSOR",
         "Extract air at a different path, cannot stand in for heater-inlet supply air."),
    "air_temperature__real_value__supply_air_outlet":
        ("°C", "supply outlet after the conditioning sections", "CANDIDATE_PROCESS_SENSOR",
         "Possible air-side process witness. General drawing and Table 2 show supply instrumentation but do not tie this export to a particular unmodified physical input."),
    "water_temperature__real_value__heater_before":
        ("°C", "liquid circuit heater_before point per place diagram", "CANDIDATE_PROCESS_SENSOR",
         "Could be a common-loop value or duplicated export. No per-AHU logger/input map or flow proof."),
    "water_temperature__real_value__heater_behind":
        ("°C", "liquid circuit heater_behind point per place diagram", "CANDIDATE_PROCESS_SENSOR",
         "Typical drawing shows a separate temperature probe; this point's physical mapping, override exclusion, fluid and flow are unverified."),
    "water_temperature__required_value__heater":
        ("°C", "liquid circuit heater requested temperature", "BAS_COMMAND",
         "Requested temperature only."),
    "signal__required_value__heater_valve":
        ("%", "heater valve regulator request", "BAS_COMMAND",
         "Fault 4 targets this actuator function. Exact exported tag/register written is unverified. No measured position."),
    "logic__required_value__heater_pump":
        ("0/1", "heater pump regulator request", "BAS_COMMAND",
         "Fault 6 targets this actuator function. Exact exported tag/register written is unverified. No independent run feedback."),
    "logic__required_value__heater":
        ("0/1", "heater request", "BAS_COMMAND", "Command-context proxy; no active operating-mode measurement."),
    "logic__required_value__chiller":
        ("0/1", "chiller request", "BAS_COMMAND", "Command-context proxy; no cooling delivery proof."),
    "logic__real_value__fan_fresh_air":
        ("0/1", "supply fan reported status", "BAS_STATUS", "Feedback wiring and airflow unverified."),
    "signal__required_value__heat_recovery_bypass":
        ("%", "heat-recovery bypass requested signal", "BAS_COMMAND", "No physical bypass feedback."),
    "pressure_dif__real_value__fan_fresh_air":
        ("Pa", "supply fan differential pressure tag", "CANDIDATE_PROCESS_SENSOR",
         "Air-side context, not coil heating or independent flow proof. Fault notes flag sensor issues."),
    "pressure_dif__real_value__supply_air_outlet":
        ("Pa", "supply outlet differential pressure tag", "CANDIDATE_PROCESS_SENSOR",
         "Air-side context, not coil heating or independent flow proof. Fault notes flag sensor issues."),
    "Time": ("Excel native time", "workbook clock", "RECORDED_METADATA", CLOCK),
    "fault": ("", "publisher row classification", "PUBLISHER_ANNOTATION", "Evaluation only."),
}
UNEXPORTED = (
    ("air temperature at heater inlet after heat recovery", "°C", "Place drawing shows heater_before on air path, absent from export."),
    ("air temperature at heater outlet before the next section", "°C", "Diagram shows heater_behind/chiller_before on air path, absent from export."),
    ("heater liquid flow or calorimetry", "", "No documented heater flow or heat-meter channel."),
    ("heater valve position feedback", "", "No measured valve position."),
    ("independent heater pump run/flow feedback", "", "No independent pump run or flow."),
    ("active operating regime", "", "No active mode enum; heat/cool commands are proxies."),
    ("per-AHU export-to-input and override record", "", "No wiring, point-address crosswalk or per-window write log in the release."),
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
                    encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_sources(raw, output):
    manifest = json.loads(Path(__file__).with_name("PUBLISHER_FILES_V1.json").read_text())
    expected = {f"{ahu}.xlsx" for ahu in AHUS} | {SCHEDULE, "Place_tag_explanation.jpg"}
    if set(manifest["files"]) != expected:
        raise ValueError("Unexpected publisher file inventory")
    for name, entry in manifest["files"].items():
        path = raw / name
        if path.stat().st_size != entry["bytes"] or digest(path) != entry["publisher_sha256"]:
            raise ValueError(f"V1 source mismatch: {name}")
        print("PASS publisher bytes", name, entry["publisher_sha256"])
    if digest(raw / PDF) != PDF_SHA:
        raise ValueError("Manuscript SHA mismatch")
    manifest["manuscript_sha256"] = PDF_SHA
    manifest["original_inventory"] = "6 AHU XLSX + 1 schedule XLSX + 1 place diagram JPG"
    write_json(output / "SOURCE_PROVENANCE_11.json", manifest)
    return manifest


def schedule(raw):
    workbook = load_workbook(raw / SCHEDULE, read_only=True, data_only=True)
    try:
        units = {row[1]: row[2] for row in workbook["Quantity explanation"].values if row[1]}
        for key, value in (("air_temperature", "°C"), ("water_temperature", "°C"),
                           ("logic", "0/1"), ("signal", "%"), ("pressure_dif", "Pa")):
            if units.get(key) != value:
                raise ValueError(f"Unexpected units: {key}")
        descriptions = {
            row[0]: {"description_sheet_row": number, "title": row[1], "protocol": row[2]}
            for number, row in enumerate(workbook["Description of fault"].values, 1) if row[0] in (4, 6)
        }
        events = []
        for number, row in enumerate(workbook["Faults Schedule"].values, 1):
            if number == 1 or not any(value is not None for value in row):
                continue
            fault, title, ahu, day, start, end, note = row
            if isinstance(day, str):
                try:
                    day = datetime.strptime(day.strip(), "%d.%m.%Y")
                except ValueError:
                    pass
            start_at = datetime.combine(day.date(), start) if isinstance(day, datetime) and isinstance(start, time) else None
            end_at = datetime.combine(day.date(), end) if isinstance(day, datetime) and isinstance(end, time) else None
            bounded = bool(start_at and end_at and start_at < end_at)
            events.append({"row": number, "fault": fault, "title": title, "ahu": ahu, "date": day,
                           "start": start_at, "end": end_at, "bounded": bounded, "note": note or ""})
        for fault in (4, 6):
            matches = [row for row in events if row["fault"] == f"Fault {fault}"]
            if len(matches) != 6 or {row["ahu"] for row in matches} != set(AHUS) or not all(r["bounded"] for r in matches):
                raise ValueError(f"Unexpected candidate schedule: Fault {fault}")
        return events, descriptions
    finally:
        workbook.close()


def finite(value):
    return type(value) in (int, float) and isfinite(value)


def labels(value):
    return " ".join(str(value or "").casefold().split())


def phase_windows(event, protocol):
    start, end = event["start"], event["end"]
    return {
        "pre": (start - timedelta(minutes=protocol["pre_minutes"]), start),
        "window": (start, end),
        "post": (end, end + timedelta(minutes=protocol["post_minutes"])),
    }


def process_workbook(raw, ahu, selected, protocol):
    phases = {event["row"]: phase_windows(event, protocol) for event in selected}
    audits = {event["row"]: {name: {
        "timestamps": [], "available": Counter(), "warm_context": 0,
        "heat_request_on": 0, "context_missing_or_invalid": 0, "labels": Counter(),
    } for name in phases[event["row"]]} for event in selected}
    bounds = [(row, name, lo, hi) for row, parts in phases.items() for name, (lo, hi) in parts.items()]
    workbook = load_workbook(raw / f"{ahu}.xlsx", read_only=True, data_only=True)
    try:
        source = workbook["Sheet1"]
        if workbook.epoch != datetime(1899, 12, 30):
            raise ValueError("Unexpected Excel epoch")
        rows = source.values
        names = next(rows)
        headers = {name: idx for idx, name in enumerate(names) if name}
        if len(headers) != len([name for name in names if name]) or not {"Time", "fault", "equipment"} <= headers.keys():
            raise ValueError(f"Invalid header in {ahu}")
        numeric_points = [key for key in POINTS if key not in ("Time", "fault") and key in headers]
        totals = Counter()
        breaks = Counter()
        first = last = None
        tick_count = 0
        context = protocol["required_context"]

        for cells in rows:
            stamp = cells[headers["Time"]]
            if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
                raise ValueError(f"Invalid native timestamp in {ahu}: row {tick_count + 2}")
            if cells[headers["equipment"]] != ahu:
                raise ValueError(f"Unexpected equipment field in {ahu}")
            tick_count += 1
            if first is None:
                first = stamp
            if last is not None and (stamp - last).total_seconds() != PERIOD:
                breaks[str(int((stamp - last).total_seconds()))] += 1
            if stamp.second or stamp.microsecond or stamp.minute % 5:
                breaks["off_grid"] += 1
            last = stamp
            present = {key for key in numeric_points if finite(cells[headers[key]])}
            totals.update(present)
            for number, name, lo, hi in bounds:
                if not lo <= stamp < hi:
                    continue
                out = audits[number][name]
                out["timestamps"].append(stamp)
                out["available"].update(present)
                bits = {key: cells[headers[key]] if key in headers else None for key in context}
                out["warm_context"] += bits == context
                out["context_missing_or_invalid"] += any(value not in (0, 1) for value in bits.values())
                out["heat_request_on"] += bits["logic__required_value__heater"] == 1
                out["labels"][labels(cells[headers["fault"]])] += 1
        if tick_count != 52705 or breaks:
            raise ValueError(f"Unexpected native time grid in {ahu}: {tick_count}, {breaks}")
        totals.update({"Time": tick_count, "fault": tick_count})
        grid = {"rows": tick_count, "first": first, "last": last, "clock": CLOCK,
                "cadence_seconds": PERIOD, "duplicate_or_irregular_steps": dict(breaks)}
        return headers, totals, grid, audits
    finally:
        workbook.close()


def summarize_event(event, all_events, audits, protocol):
    parts = phase_windows(event, protocol)
    start, end = event["start"], event["end"]
    others = [row for row in all_events if row["ahu"] == event["ahu"] and row["row"] != event["row"]]
    before = [row for row in others if row["bounded"] and row["end"] <= start]
    after = [row for row in others if row["bounded"] and row["start"] >= end]
    previous = max(before, key=lambda row: row["end"], default=None)
    following = min(after, key=lambda row: row["start"], default=None)
    same_day = [row for row in others if isinstance(row["date"], datetime) and row["date"].date() == start.date()]
    overlaps = {key: [row["row"] for row in same_day if row["bounded"] and row["start"] < hi and lo < row["end"]]
                for key, (lo, hi) in parts.items()}
    unresolved_same_day = [row["row"] for row in same_day if not row["bounded"]]
    unresolved_unknown_day = [row["row"] for row in others if not isinstance(row["date"], datetime)]
    known_labels = {labels(event["fault"]), labels(event["title"])}
    reported = {}
    phase_a_detail = {}
    for name, (lo, hi) in parts.items():
        audit = audits[name]
        times = audit["timestamps"]
        expected = int((hi - lo).total_seconds() // PERIOD)
        if len(times) != expected or not times or any(
            (next_stamp - stamp).total_seconds() != PERIOD for stamp, next_stamp in zip(times, times[1:])
        ):
            raise ValueError(f"Unqualified window grid: schedule row {event['row']}, {name}")
        histogram = audit["labels"]
        phase_a_detail[name] = {
            "start_inclusive": lo, "end_exclusive": hi,
            "first_native_tick": times[0], "last_native_tick": times[-1],
            "ticks": len(times), "finite_by_native_header": dict(audit["available"]),
            "all_context_bits_match": audit["warm_context"], "heat_request_on": audit["heat_request_on"],
            "missing_or_invalid_context": audit["context_missing_or_invalid"],
            "publisher_label_histogram_evaluation_only": dict(histogram),
        }
        reported.update({
            name + "_ticks": len(times),
            name + "_warm_context_ticks": audit["warm_context"],
            name + "_heat_request_on_ticks": audit["heat_request_on"],
            name + "_invalid_context_ticks": audit["context_missing_or_invalid"],
        })
    labels_in_window = audits["window"]["labels"]
    report = {
        "site": SITE, "ahu": event["ahu"], "schedule_row": event["row"], "fault_id": event["fault"],
        "schedule_title": event["title"], "start_naive_inclusive": start, "end_naive_exclusive": end,
        "clock": CLOCK, "publisher_note": event["note"], "source_grid": "CONTIGUOUS_300S",
        **reported,
        "schedule_overlap_rows_pre_window_post": json.dumps(overlaps, sort_keys=True),
        "unresolved_same_day_schedule_rows": json.dumps(unresolved_same_day),
        "unresolved_unknown_day_same_ahu_rows": json.dumps(unresolved_unknown_day),
        "previous_same_ahu_row": previous["row"] if previous else "",
        "gap_since_previous_minutes": int((start - previous["end"]).total_seconds() / 60) if previous else "",
        "next_same_ahu_row": following["row"] if following else "",
        "gap_to_next_minutes": int((following["start"] - end).total_seconds() / 60) if following else "",
        "washout": "UNKNOWN",
        "exact_id_or_title_ticks_evaluation_only": sum(labels_in_window[label] for label in known_labels),
        "other_label_ticks_evaluation_only": sum(n for key, n in labels_in_window.items()
                                                  if key not in known_labels | {"", "no fault"}),
        "window_label_histogram_evaluation_only": json.dumps(labels_in_window, sort_keys=True),
        "eligibility": "STOP",
        "primary_reason": "STOP_MANIPULATION_LINEAGE_UNKNOWN",
        "independent_reason": "STOP_NO_INDEPENDENT_PROCESS_WITNESS",
        "pre_window_command_context": "PROXY_COMPLETE" if all(
            audits[part]["warm_context"] == len(audits[part]["timestamps"]) for part in ("pre", "window")
        ) else "PROXY_INCOMPLETE_OR_NOT_WARM",
        "available_context_note": "NO_QUALIFIED_AIR_PAIR; AHU2/8 missing heat/cool/SAT" if event["ahu"] in ("AHU2", "AHU8")
                                  else "NO_QUALIFIED_AIR_PAIR",
        "selection": "ABSTAIN",
        "phase_b": "NOT_RUN",
    }
    return report, phase_a_detail


def main(raw, freeze_dir, output):
    prereg_hashes = {name: digest(freeze_dir / name) for name in FREEZE}
    if prereg_hashes != FREEZE:
        raise ValueError("Preregistration hash mismatch")
    created = datetime.fromisoformat((freeze_dir / "PREREGISTERED_11_CREATED_AT.txt").read_text().strip())
    run_at = datetime.now(timezone.utc)
    if created.tzinfo is None or created >= run_at:
        raise ValueError("Freeze receipt must precede source scan")
    protocol = json.loads((freeze_dir / "PREREGISTERED_11.json").read_text())
    manifest = verify_sources(raw, output)
    events, descriptions = schedule(raw)
    selected = [event for number in protocol["candidate_order"] for event in events if event["fault"] == f"Fault {number}"]
    signal_ledger, event_ledger = [], []
    grids, windows = {}, {}
    for ahu in AHUS:
        candidates = [event for event in selected if event["ahu"] == ahu]
        headers, totals, grid, audits = process_workbook(raw, ahu, candidates, protocol)
        grids[ahu] = grid
        workbook_sha = manifest["files"][f"{ahu}.xlsx"]["publisher_sha256"]
        for header, (unit, position, role, caveat) in POINTS.items():
            available = header in headers and totals[header] > 0
            injection = {
                "signal__required_value__heater_valve": "FAULT_4_ACTUATOR_FUNCTION_TARGET; EXACT_TAG_WRITE_UNVERIFIED",
                "logic__required_value__heater_pump": "FAULT_6_ACTUATOR_FUNCTION_TARGET; EXACT_TAG_WRITE_UNVERIFIED",
            }.get(header, "NOT_LISTED_AS_TARGET; PER_WINDOW_OVERRIDE_EXCLUSION_UNVERIFIED"
                        if role == "CANDIDATE_PROCESS_SENSOR" else "NOT_ATTESTED")
            signal_ledger.append({
                "site": SITE, "ahu": ahu, "workbook": f"{ahu}.xlsx", "sheet": "Sheet1",
                "source_sha256": workbook_sha, "native_header": header if header in headers else "",
                "point_or_expected_header": header, "native_unit": unit, "position": position,
                "role": role, "manipulation": injection,
                "availability": "AVAILABLE" if available else "MISSING",
                "availability_detail": ("NUMERIC_OR_METADATA_PRESENT" if available else
                                        "NO_FINITE_VALUES" if header in headers else "NO_COLUMN"),
                "semantic_status": ("SEMANTIC_UNVERIFIED" if available else "MISSING") if role == "CANDIDATE_PROCESS_SENSOR"
                                   else "NATIVE_ROLE_IDENTIFIED",
                "nonmissing_or_finite_rows": totals[header],
                "caveat": caveat,
            })
        for position, unit, caveat in UNEXPORTED:
            signal_ledger.append({
                "site": SITE, "ahu": ahu, "workbook": f"{ahu}.xlsx", "sheet": "Sheet1",
                "source_sha256": workbook_sha, "native_header": "", "point_or_expected_header": position,
                "native_unit": unit, "position": position, "role": "ABSTAIN",
                "manipulation": "UNKNOWN", "availability": "MISSING",
                "availability_detail": "NO_QUALIFIED_EXPORTED_POINT_OR_DOCUMENTATION",
                "semantic_status": "MISSING", "nonmissing_or_finite_rows": 0, "caveat": caveat,
            })
        for event in candidates:
            report, detail = summarize_event(event, events, audits[event["row"]], protocol)
            event_ledger.append(report)
            windows[str(event["row"])] = detail
        print(f"PASS availability/time audit {ahu}: {grid['rows']} native ticks")
    event_ledger.sort(key=lambda row: row["schedule_row"])
    write_csv(output / "SOURCE_MECHANISM_LEDGER.csv", signal_ledger)
    write_csv(output / "EVENT_ELIGIBILITY_11.csv", event_ledger)
    write_json(output / "GAP_CLOCK_CONTEXT_11.json", {
        "prereg_created_local": created.isoformat(), "audit_started_utc": run_at.isoformat(),
        "verified_prereg_hashes": prereg_hashes, "clock": CLOCK, "workbooks": grids,
        "eligible_windows": 0, "windows": windows, "publisher_protocol": descriptions,
        "site_count": 1, "candidate_schedule_days": 2, "candidate_schedule_rows": 12,
        "assessment": {
            "phase_a": "STOP", "phase_b": "NOT_RUN", "selected_schedule_row": None,
            "selected_comparison_window": None, "quantitative_response_evaluations": 0,
        },
    })
    print("STOP 12/12 schedule entries screened. No temperature values or response estimates exported.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("freeze_dir", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
