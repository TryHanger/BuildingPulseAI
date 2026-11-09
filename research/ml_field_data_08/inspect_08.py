"""Read-only qualification of the eight pinned Nehasil Mendeley files."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
from datetime import datetime, timedelta
from hashlib import file_digest
import json
from math import isfinite
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

MANIFEST = Path(__file__).with_name("PUBLISHER_FILES_V1.json")
SCHEDULE = "Faults_schedule_and_description.xlsx"
PAPER = {
    "record": "https://dspace.cvut.cz/entities/publication/35d10945-7123-4cdc-8367-50bfdb4c1052",
    "download": "https://dspace.cvut.cz/server/api/core/bitstreams/2f9d64ab-bbd6-487c-b120-3d01bcbf4af2/content",
    "sha256": "4a03914e8064ae3b42ffce9a806a724f7451bae7596d940ff3884b6c50a072ef",
    "publisher_md5": "a4749a55c2366deb298a3cae6104c504",
    "bytes": 1814037,
    "citation": "Nehasil et al., 2021, DOI 10.1016/j.enbuild.2021.110781, accepted manuscript, sections 3.1-3.3 and Tables 2-3",
}
AIRFLOW_M3H = {"AHU1": 7850, "AHU2": 4560, "AHU8": 3680, "AHU18": 4420, "AHU23": 4050, "AHU24": 2270}
SAT = "air_temperature__real_value__supply_air_outlet"
EXHAUST = "air_temperature__real_value__exahust_air_inlet"
EXHAUST_SP = "air_temperature__required_value__exahust_air_inlet"
FAN = "logic__real_value__fan_fresh_air"
EXHAUST_FAN = "logic__real_value__fan_exahust_air"
HEAT = "logic__required_value__heater"
COOL = "logic__required_value__chiller"
ABSENT = {
    "MAT": "True mixed-air point; heat-recovery outlet or between-coils cannot substitute",
    "OAT": "Outdoor dry-bulb measurement, not present in worksheet",
    "ACTIVE_SAT_SP": "Required value at supply outlet is absent; exhaust SP and supply min/max are different roles",
    "ACTUAL_SUPPLY_FAN_DRIVE": "No actual VFD speed/drive feedback; required signal is a command",
    "ACTUAL_VALVE_POSITION": "Required valve signal is a command, not position feedback",
    "VERIFIED_OPERATING_MODE": "No active mode enum; heating/cooling requests are proxies",
    "MEASURED_AIR_BETWEEN_COILS": "No air-side intermediate temperature; water temperatures are distinct",
    "MEASURED_SUPPLY_FAN_RUN_PROOF": "BAS logic real_value is present; independent contact/tachometer lineage is unverified",
}


class QualificationError(ValueError):
    pass


def sha(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def qualify_source(raw, manifest):
    verified = {}
    for name, spec in manifest["files"].items():
        path = raw / name
        if not path.is_file():
            raise QualificationError("STOP_SOURCE_UNAVAILABLE:" + name)
        actual = sha(path)
        if path.stat().st_size != spec["bytes"] or actual != spec["publisher_sha256"]:
            raise QualificationError("STOP_SOURCE_SHA_MISMATCH:" + name)
        verified[name] = {**spec, "verified_sha256": actual}
    return verified


def sampling_status(intervals, duplicates, reversed_ticks):
    if duplicates or reversed_ticks or not intervals:
        return "STOP_UNQUALIFIED_CLOCK"
    if intervals != {60: sum(intervals.values())}:
        return "STOP_NON_MINUTE_CADENCE"
    return "MINUTE_GRID_ONLY_OTHER_GATES_REQUIRED"


def normalize_label(value):
    if not isinstance(value, str):
        return "UNKNOWN"
    label = value.strip().lower()
    match = re.fullmatch(r"fault\s+(\d+)", label)
    if match:
        return f"Fault {int(match[1])}"
    return label if label else "UNKNOWN"


def event_label_matches(label, event):
    """The telemetry uses descriptions while the schedule also has numeric fault IDs."""
    return label in {event["fault_id"], normalize_label(event["title"])}


def write_json(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str, allow_nan=False)
        stream.write("\n")


def write_csv(path, rows):
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_schedule(path):
    with closing(load_workbook(path, read_only=True, data_only=True)) as wb:
        events = []
        for row_number, row in enumerate(wb["Faults Schedule"].values, 1):
            if row_number == 1 or all(value is None for value in row):
                continue
            fault, title, ahu, date, start, end, note = row
            day = date.date() if isinstance(date, datetime) else datetime.strptime(date, "%d.%m.%Y").date()
            left, right = datetime.combine(day, start), datetime.combine(day, end)
            status = "BOUNDED_NAIVE" if right > left else "UNRESOLVED_END_NOT_AFTER_START"
            events.append({"schedule_row": row_number, "ahu": ahu, "fault_id": normalize_label(fault), "title": title,
                           "original_date": str(date), "start_naive": left, "end_naive": right, "status": status,
                           "publisher_note": note, "repair_or_washout_verified": False})
        units = {row[1]: row[2] for row in wb["Quantity explanation"].values if row[1] and row[1] != "Quantity tag"}
        samples = {sheet.title: [list(row) for row in list(sheet.iter_rows(max_row=4, values_only=True))]
                   for sheet in wb}
    return events, units, samples


def roles(header):
    exact = {
        SAT: ("SAT", "BAS_FIELD_MEASUREMENT", "Supply outlet after conditioning; susceptible to documented injected sensor values"),
        EXHAUST: ("RAT_CANDIDATE", "BAS_FIELD_MEASUREMENT", "Extract inlet from occupied space, upstream of plate recovery; not MAT"),
        EXHAUST_SP: ("EXHAUST_SP", "BAS_SETPOINT_EXHAUST", "Required extract-inlet temperature; no evidence that it is active SAT SP"),
        FAN: ("SF_BAS_STATUS", "BAS_STATUS_UNVERIFIED_RUN_PROOF", "Supply fan binary BAS status; feedback wiring not independently documented"),
        EXHAUST_FAN: ("EF_BAS_STATUS", "BAS_STATUS_UNVERIFIED_RUN_PROOF", "Exhaust fan status; not a supply status or return recirculation fan"),
        HEAT: ("HEAT_REQUEST", "BAS_COMMAND", "Heater request; not measured heating or active operating mode"),
        COOL: ("COOL_REQUEST", "BAS_COMMAND", "Chiller request; not measured cooling or active operating mode"),
        "Time": ("CLOCK", "RECORDED_METADATA", "Naive workbook time; offset and DST convention undocumented"),
        "equipment": ("EQUIPMENT_ID", "RECORDED_METADATA", "Equipment ID, grouping only"),
        "fault": ("FAULT_LABEL", "ANNOTATION_EXCLUDED_FROM_INPUT", "Publisher label; not independent healthy truth"),
    }
    if header in exact:
        return exact[header]
    parts = header.split("__")
    if len(parts) != 3:
        return "", "UNKNOWN_ROLE", "Unmapped original header"
    quantity, kind, place = parts
    if kind in {"min", "max"}:
        return "", "BAS_LIMIT", f"{place}; configured {kind} limit, not active setpoint"
    if kind == "required_value":
        role = "BAS_SETPOINT" if quantity in {"air_temperature", "water_temperature", "relative_humidity"} else "BAS_COMMAND"
        return "", role, f"{place}; controller request, no measured position or proof"
    if quantity == "water_temperature":
        return "", "BAS_FIELD_MEASUREMENT", f"{place}; water-side point, not an air measurement"
    return "", "BAS_STATUS" if quantity == "logic" else "BAS_REPORTED_MEASUREMENT", place


def clock_probe(stamp):
    # Only an ambiguity probe. Do not assign a zone or repair an export.
    zone = ZoneInfo("Europe/Prague")
    valid = {stamp.replace(tzinfo=zone, fold=fold).timestamp() for fold in (0, 1)
             if datetime.fromtimestamp(stamp.replace(tzinfo=zone, fold=fold).timestamp(), zone).replace(tzinfo=None) == stamp}
    return "NONEXISTENT" if not valid else "AMBIGUOUS" if len(valid) == 2 else "UNAMBIGUOUS"


def inspect_unit(path, events, units, verified):
    ahu = path.stem
    events_for_day = defaultdict(list)
    for event in events:
        if event["ahu"] == ahu:
            events_for_day[event["start_naive"].date()].append(event)
    scheduled_site_days = {event["start_naive"].date() for event in events}
    stats, labels, intervals, fan_values, proxy_modes = Counter(), Counter(), Counter(), Counter(), Counter()
    days, seen, sp_no_fault = {}, set(), set()
    misses, numeric_limits = Counter(), {}
    samples, first, previous, previous_fan, last = [], None, None, None, None
    with closing(load_workbook(path, read_only=True, data_only=True)) as wb:
        sheet = wb["Sheet1"]
        data = iter(sheet.values)
        header = next(data)
        if len(set(header)) != len(header) or not {"Time", "fault", "equipment"} <= set(header):
            raise QualificationError("STOP_UNQUALIFIED_HEADERS:" + ahu)
        sheet_shapes = {s.title: [s.max_row, s.max_column] for s in wb}
        idx = {name: index for index, name in enumerate(header)}
        for original_row, values in enumerate(data, 2):
            if not any(value is not None for value in values):
                continue
            stats["rows"] += 1
            ts = values[idx["Time"]]
            if not isinstance(ts, datetime) or ts.tzinfo is not None:
                stats["invalid_timestamps"] += 1
                continue
            first = first or ts
            last = ts
            day = ts.date()
            row = days.setdefault(day, Counter())
            row["rows"] += 1
            if ts in seen:
                stats["duplicate_timestamps"] += 1
                row["duplicate_timestamps"] += 1
            seen.add(ts)
            fan, heat, cool = (values[idx[key]] if key in idx else None for key in (FAN, HEAT, COOL))
            fan_values[str(fan)] += 1
            mode = "UNKNOWN_COMMAND_PAIR" if heat not in (0, 1) or cool not in (0, 1) else f"HEAT_{int(heat)}_COOL_{int(cool)}"
            proxy_modes[mode] += 1
            row["heat_requested_rows"] += heat == 1
            row["cool_requested_rows"] += cool == 1
            if previous is not None:
                elapsed = int((ts - previous).total_seconds())
                intervals[elapsed] += 1
                if elapsed == 300 and fan in (0, 1) and previous_fan in (0, 1) and fan != previous_fan:
                    stats["adjacent_300s_bAS_fan_transitions"] += 1
            previous, previous_fan = ts, fan
            if values[idx["equipment"]] != ahu:
                stats["equipment_id_mismatches"] += 1
            label = normalize_label(values[idx["fault"]])
            labels[label] += 1
            active = [event for event in events_for_day[day] if event["status"] == "BOUNDED_NAIVE"
                      and event["start_naive"] <= ts < event["end_naive"]]
            if active:
                row["in_scheduled_event_rows"] += 1
                for event in active:
                    event["matched_grid_rows"] = event.get("matched_grid_rows", 0) + 1
                    event["exact_id_or_title_label_rows"] = event.get("exact_id_or_title_label_rows", 0) + event_label_matches(label, event)
                    event["publisher_no_fault_rows"] = event.get("publisher_no_fault_rows", 0) + (label == "no fault")
                    extract = values[idx[EXHAUST_FAN]] if EXHAUST_FAN in idx else None
                    event["both_fan_status_available_rows"] = event.get("both_fan_status_available_rows", 0) + (
                        fan in (0, 1) and extract in (0, 1))
            if label == "no fault":
                row["publisher_no_fault_rows"] += 1
                if fan == 1:
                    row["publisher_no_fault_bAS_fan_on_rows"] += 1
                    if not active:
                        row["candidate_no_fault_fan_on_outside_schedule_rows"] += 1
                    if values[idx[EXHAUST_SP]] is not None:
                        sp_no_fault.add(str(values[idx[EXHAUST_SP]]))
                if active:
                    row["no_fault_inside_schedule_rows"] += 1
            elif label != "UNKNOWN":
                row["publisher_fault_rows"] += 1
                if not active:
                    row["fault_label_outside_schedule_rows"] += 1
                    if any(event["status"] == "BOUNDED_NAIVE" and ts == event["end_naive"]
                           for event in events_for_day[day]):
                        row["fault_label_at_scheduled_end_rows"] += 1
            else:
                row["unknown_label_rows"] += 1
            for key, value in zip(header, values, strict=True):
                if value is None:
                    misses[key] += 1
                elif isinstance(value, (int, float)) and isfinite(value):
                    low, high = numeric_limits.get(key, (value, value))
                    numeric_limits[key] = (min(value, low), max(value, high))
            if len(samples) < 2:
                samples.append({"row": original_row, "values": list(values)})
    reversed_ticks = sum(count for sec, count in intervals.items() if sec < 0)
    status = sampling_status(intervals, stats["duplicate_timestamps"], reversed_ticks)
    cadence = intervals.most_common(1)[0][0]
    dst = Counter(clock_probe(stamp) for stamp in seen if stamp.hour in (1, 2, 3))
    ledger = []
    for day, row in sorted(days.items()):
        contamination = []
        if events_for_day.get(day):
            contamination.append("SCHEDULED_EVENT_ON_AHU_DAY")
        elif day in scheduled_site_days:
            contamination.append("OTHER_AHU_SCHEDULED_EVENT_SAME_SITE_DAY")
        if row["publisher_fault_rows"]:
            contamination.append("PUBLISHER_FAULT_LABEL_PRESENT")
        if row["no_fault_inside_schedule_rows"] or row["fault_label_outside_schedule_rows"]:
            contamination.append("SCHEDULE_LABEL_DISAGREEMENT")
        ledger.append({"ahu": ahu, "naive_calendar_day": str(day), "clock_basis": "TIMEZONE_UNVERIFIED",
                       **{name: row[name] for name in ("rows", "duplicate_timestamps", "publisher_no_fault_rows",
                          "publisher_no_fault_bAS_fan_on_rows", "candidate_no_fault_fan_on_outside_schedule_rows",
                          "in_scheduled_event_rows", "no_fault_inside_schedule_rows", "fault_label_outside_schedule_rows",
                          "fault_label_at_scheduled_end_rows", "publisher_fault_rows", "unknown_label_rows", "heat_requested_rows", "cool_requested_rows")},
                       "contamination": "|".join(contamination) or "NO_KNOWN_SCHEDULE_CONFLICT",
                       "independently_certified_healthy": "UNKNOWN", "qualifies_minute_training": False})
    mapped = []
    for key in (*header, *ABSENT):
        absent = key in ABSENT
        canonical, role, description = (key, "ABSENT_OR_NOT_VERIFIED", ABSENT[key]) if absent else roles(key)
        unit = "" if absent else units.get(key.split("__")[0], "")
        conversion = "C_to_F: x*1.8+32; not applied" if unit == "°C" else ""
        mapped.append({"ahu": ahu, "file": path.name, "sheet": "Sheet1", "sha256": verified["verified_sha256"],
                       "paper_nominal_airflow_m3h": AIRFLOW_M3H[ahu],
                       "paper_topology": "Plate recovery with bypass, heater/cooler" +
                                         ("; steam humidifier and intercooler geometry" if ahu == "AHU8" else ""),
                       "original_header": "" if absent else key, "candidate": canonical,
                       "native_unit": unit, "validated_conversion": conversion, "physical_point_or_caveat": description,
                       "lineage": "Absent from export or proof missing" if absent else "Publisher workbook tags + unit legend + place schematic",
                       "role": role, "dominant_interval_s": cadence,
                       "missing_rows": "" if absent else misses[key],
                       "nonmissing_rows": "" if absent else stats["rows"] - misses[key],
                       "min_native": numeric_limits.get(key, ("", ""))[0], "max_native": numeric_limits.get(key, ("", ""))[1]})
    return {
        "sampling_gate": status, "first": str(first), "last": str(last), "dominant_interval_s": cadence,
        "time_delta_seconds": dict(sorted(intervals.items())), "reversed_intervals": reversed_ticks,
        "duplicate_timestamps": stats["duplicate_timestamps"], "invalid_timestamps": stats["invalid_timestamps"],
        "rows": stats["rows"], "observed_calendar_days": len(days), "distinct_timestamps": len(seen),
        "timezone": "UNVERIFIED_NAIVE", "europe_prague_dst_probe_not_assigned": dict(dst),
        "equipment_id_mismatches": stats["equipment_id_mismatches"],
        "label_counts": labels, "fan_status_values": fan_values, "command_context_counts": proxy_modes,
        "adjacent_300s_bAS_fan_transitions": stats["adjacent_300s_bAS_fan_transitions"],
        "publisher_no_fault_bAS_fan_on_rows": sum(row["publisher_no_fault_bAS_fan_on_rows"] for row in ledger),
        "publisher_no_fault_bAS_fan_on_calendar_days": sum(row["publisher_no_fault_bAS_fan_on_rows"] > 0 for row in ledger),
        "candidate_no_fault_fan_on_outside_schedule_rows": sum(row["candidate_no_fault_fan_on_outside_schedule_rows"] for row in ledger),
        "no_fault_inside_schedule_rows": sum(row["no_fault_inside_schedule_rows"] for row in ledger),
        "fault_label_outside_schedule_rows": sum(row["fault_label_outside_schedule_rows"] for row in ledger),
        "fault_label_at_scheduled_end_rows": sum(row["fault_label_at_scheduled_end_rows"] for row in ledger),
        "exhaust_sp_values_on_labeled_no_fault_fan_on": sorted(sp_no_fault, key=float),
        "active_sat_sp_levels": None, "active_sat_sp_resolution": "UNKNOWN",
        "independently_certified_healthy_days": 0, "independently_certified_healthy_runs": 0,
        "missing_sat_rows": misses[SAT], "worksheet_shapes": sheet_shapes,
    }, mapped, ledger, {"headers": header, "samples": samples}


def main(raw, output, manuscript=None):
    manifest = json.loads(MANIFEST.read_text())
    verified = qualify_source(raw, manifest)
    if manuscript is not None:
        if manuscript.stat().st_size != PAPER["bytes"] or sha(manuscript) != PAPER["sha256"]:
            raise QualificationError("STOP_MANUSCRIPT_SHA_MISMATCH")
    events, units, samples = read_schedule(raw / SCHEDULE)
    profiles, signals, ledger = {}, [], []
    samples = {SCHEDULE: samples}
    for name in sorted(verified):
        if not name.startswith("AHU"):
            continue
        ahu = Path(name).stem
        profile, mapped, daily, example = inspect_unit(raw / name, events, units, verified[name])
        profiles[ahu], samples[name] = profile, example
        signals.extend(mapped)
        ledger.extend(daily)
    for event in events:
        event["matched_grid_rows"] = event.get("matched_grid_rows", 0)
        for key in ("exact_id_or_title_label_rows", "publisher_no_fault_rows", "both_fan_status_available_rows"):
            event[key] = event.get(key, 0)
    samples["Place_tag_explanation.jpg"] = {
        "verified_sha256": verified["Place_tag_explanation.jpg"]["verified_sha256"],
        "observed_content": "Plate recovery with separate supply/extract air streams; labels distinguish chiller_behind water and air points.",
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "FIELD_SOURCE_PROVENANCE_08.json", {
        **manifest, "files": verified, "units_from_quantity_explanation": units,
        "article_manuscript": {**PAPER, "file_verified_in_this_run": manuscript is not None},
        "license_notes": "CC BY 4.0 applies to Mendeley data; manuscript is separate",
        "training_or_scoring_executed": False, "field_building_count": 1,
        "provenance": {"telemetry": "Publisher BMS, possible injected or overridden values",
                       "labels": "Publisher workbook and separate scheduled interventions",
                       "independent_normal_validation": "NOT_PROVIDED",
                       "sensor_calibration_and_active_loop_mapping": "NOT_PROVIDED"},
    })
    write_json(output / "WORKBOOK_AUDIT_08.json", {"units": profiles, "schedule_nonblank_events": len(events),
               "schedule_fault_ids": len({event["fault_id"] for event in events}), "independent_buildings": 1})
    write_json(output / "SOURCE_SAMPLES_08.json", samples)
    write_csv(output / "FIELD_SIGNAL_MAP_08.csv", signals)
    write_csv(output / "HEALTHY_WINDOW_LEDGER_08.csv", ledger)
    write_csv(output / "EVENT_LEDGER_08.csv", events)
    print(f"PASS {len(verified)} original file hashes; {len(profiles)} units; {len(events)} bounded or flagged schedule rows; no scoring")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manuscript", type=Path)
    try:
        main(**vars(parser.parse_args()))
    except QualificationError as error:
        parser.exit(2, str(error) + "\n")
