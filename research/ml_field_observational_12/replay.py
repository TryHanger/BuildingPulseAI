"""Offline Stage12. Preparation selects and seals the windows before calculation."""
import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

PREFIX = "FIELD_OBSERVATIONAL_12_PREREG"
PREREG_HASHES = {
    ".md": "48372f20f470a9833b8d75bae8a8d194df8f22ccd1fc6752684c6a42c9d678bf",
    ".json": "2eff3e0a6c5613882b6e21291f3b8242f13309c84bf16136eaef9289af25c4c1",
}
SITE = "CTU-UCEEB_Bustehrad"
SCHEDULE = "Faults_schedule_and_description.xlsx"
UNITS = {"air_temperature": "°C", "water_temperature": "°C", "signal": "%", "logic": "0/1"}
PARTS = ("PRE", "WINDOW", "POST")
DIFF = "reported_heater_behind_minus_before"
TZ = ZoneInfo("Asia/Qyzylorda")
PREPARED_FILES = ("ELIGIBILITY_12.csv", "CONTROLS_12.csv", "SELECTION_12.json",
                  "FEASIBILITY_12.csv", "RAW_SLICE_12.csv", "PUBLISHER_ANNOTATIONS_12.csv")


class Stop(ValueError):
    pass


@dataclass(frozen=True)
class Event:
    row: int
    ahu: str
    day: date
    start: datetime | None
    end: datetime | None
    fault: str
    title: str
    note: str


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def finite(value):
    return type(value) in (int, float) and isfinite(value)


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def table(path, rows, fields=None):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_protocol(folder):
    for suffix, expected in PREREG_HASHES.items():
        if digest(folder / (PREFIX + suffix)) != expected:
            raise Stop("STOP_PREREG_SHA_MISMATCH")
    receipt = datetime.fromisoformat((folder / (PREFIX + "_CREATED_AT.txt")).read_text().strip())
    if receipt.tzinfo is None or receipt >= datetime.now(TZ):
        raise Stop("STOP_PREREG_CLOCK")
    return json.loads((folder / (PREFIX + ".json")).read_text())


def verify_sources(raw, folder, protocol):
    manifest_path = folder / "evidence/SOURCE_PROVENANCE_11.json"
    if digest(manifest_path) != protocol["source_manifest_sha256"]:
        raise Stop("STOP_SOURCE_MANIFEST_MISMATCH")
    manifest = json.loads(manifest_path.read_text())
    if manifest["dataset_doi"] != protocol["dataset_doi"] or manifest["version"] != 1:
        raise Stop("STOP_SOURCE_MANIFEST_MISMATCH")
    for name, entry in manifest["files"].items():
        path = raw / name
        if not path.is_file():
            raise Stop(f"STOP_SOURCE_UNAVAILABLE {name}")
        if path.stat().st_size != entry["bytes"] or digest(path) != entry["publisher_sha256"]:
            raise Stop(f"STOP_SOURCE_SHA_MISMATCH {name}")
    return manifest


def signal_columns(protocol):
    temperatures = (protocol["sat"], *protocol["secondary"])
    commands = tuple(protocol["commands"])
    status = protocol["status"]
    if (any(key.split("__")[1:2] != ["real_value"] or key.split("__")[0] not in
            ("air_temperature", "water_temperature") for key in temperatures)
            or any(key.split("__")[1:2] != ["required_value"] for key in commands)
            or status != "logic__real_value__fan_fresh_air"):
        raise Stop("STOP_CHANNEL_ROLE_MISMATCH")
    return temperatures, commands, status


def read_schedule(raw):
    book = load_workbook(raw / SCHEDULE, read_only=True, data_only=True)
    try:
        legend = {row[1]: row[2] for row in book["Quantity explanation"].values if row[1]}
        if any(legend.get(key) != value for key, value in UNITS.items()):
            raise Stop("STOP_SOURCE_UNIT_MISMATCH")
        rows = iter(book["Faults Schedule"].values)
        next(rows)
        events = []
        for number, values in enumerate(rows, 2):
            if not any(value is not None for value in values):
                continue
            fault, title, ahu, day, start, end, note = values
            if isinstance(day, datetime):
                day = day.date()
            elif isinstance(day, str):
                try:
                    day = datetime.strptime(day.strip(), "%d.%m.%Y").date()
                except ValueError as error:
                    raise Stop(f"STOP_UNRESOLVED_SCHEDULE_ROW {number}") from error
            if not isinstance(day, date) or ahu not in {"AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24"}:
                raise Stop(f"STOP_UNRESOLVED_SCHEDULE_ROW {number}")
            if isinstance(start, time) and isinstance(end, time) and start < end:
                lo, hi = datetime.combine(day, start), datetime.combine(day, end)
            else:
                lo = hi = None
            events.append(Event(number, ahu, day, lo, hi, fault, title, note or ""))
        return events
    finally:
        book.close()


def expected_ticks(day, protocol):
    boundaries = [datetime.combine(day, time.fromisoformat(value)) for value in protocol["boundaries"]]
    step = timedelta(seconds=protocol["cadence_seconds"])
    return {part: [lo + i * step for i in range((hi - lo) // step)]
            for part, lo, hi in zip(PARTS, boundaries, boundaries[1:])}


def telemetry(raw, protocol, columns):
    book = load_workbook(raw / (protocol["ahu"] + ".xlsx"), read_only=True, data_only=True)
    try:
        if book.epoch != datetime(1899, 12, 30):
            raise Stop("STOP_SOURCE_CLOCK")
        rows = iter(book["Sheet1"].values)
        headers = tuple(next(rows))
        if any(headers.count(key) != 1 for key in ("Time", *columns)):
            raise Stop("STOP_SOURCE_HEADER")
        indices = [headers.index(key) for key in ("Time", *columns)]
        for row in rows:
            yield tuple(row[index] for index in indices)
    finally:
        book.close()


def read_masks(raw, protocol):
    previous = None
    masks = {}
    context = protocol["required_context"]
    first = None
    for stamp, sat, *bits in telemetry(raw, protocol, (protocol["sat"], *context)):
        if (not isinstance(stamp, datetime) or stamp.tzinfo is not None
                or stamp.second or stamp.microsecond or stamp.minute % 5
                or (previous is not None and stamp <= previous)):
            raise Stop("STOP_SOURCE_CLOCK")
        first = stamp if first is None else first
        previous = stamp
        if stamp.weekday() == date.fromisoformat(protocol["event_date"]).weekday():
            masks[stamp] = (finite(sat), all(value == target for value, target in zip(bits, context.values())))
    if first is None:
        raise Stop("STOP_SOURCE_CLOCK")
    return first, previous, masks


def qualify(day, protocol, events, masks, *, primary=False):
    ticks = expected_ticks(day, protocol)
    lo, hi = ticks["PRE"][0], ticks["POST"][-1] + timedelta(seconds=protocol["cadence_seconds"])
    relevant = [e for e in events if e.ahu == protocol["ahu"] and not (primary and e.row == protocol["schedule_row"])]
    overlaps = [e.row for e in relevant if e.start is not None and e.start < hi and lo < e.end]
    unresolved = [e.row for e in relevant if e.start is None and e.day == day]
    blocked = [e for e in events if abs((e.day - day).days) <= protocol["date_buffer_days"] and not primary]
    counts = {}
    for part, stamps in ticks.items():
        found = [masks[stamp] for stamp in stamps if stamp in masks]
        counts.update({f"{part}_native": len(found), f"{part}_missing_ticks": len(stamps) - len(found),
                       f"{part}_sat_missing": sum(not mask[0] for mask in found),
                       f"{part}_context_mismatch": sum(not mask[1] for mask in found)})
    reasons = [reason for reason, condition in (
        ("SITE_EVENT_DAY_OR_BUFFER", bool(blocked)), ("AHU_SCHEDULE_OVERLAP", bool(overlaps)),
        ("AHU_UNBOUNDED_SCHEDULE", bool(unresolved)),
        ("GRID_INCOMPLETE", any(counts[f"{part}_missing_ticks"] for part in PARTS)),
        ("SAT_NOT_FINITE", any(counts[f"{part}_sat_missing"] for part in PARTS)),
        ("COMMAND_CONTEXT_MISMATCH", any(counts[f"{part}_context_mismatch"] for part in PARTS[:2])),
    ) if condition]
    return {
        "date": day.isoformat(), "relative_weeks": (day - date.fromisoformat(protocol["event_date"])).days // 7,
        **counts, "site_blocking_dates": "|".join(sorted({e.day.isoformat() for e in blocked})),
        "ahu_overlap_rows": "|".join(map(str, overlaps)), "ahu_unbounded_rows": "|".join(map(str, unresolved)),
        "eligible": not reasons, "reasons": "|".join(reasons),
    }


def select(event, ledger, limit):
    passed = sorted((row for row in ledger if row["eligible"]),
                    key=lambda row: (abs(row["relative_weeks"]), row["date"]))
    if not event["eligible"]:
        return [], "STOP_PRIMARY_INELIGIBLE"
    if not passed:
        return [(event["date"], "event")], "STOP_NO_COMPARATOR"
    selected = [(event["date"], "event"), (passed[0]["date"], "comparison")]
    selected.extend((row["date"], f"negative_control_{i}") for i, row in enumerate(passed[1:1 + limit], 1))
    return selected, "DESCRIPTIVE_OBSERVED"


def extract(raw, protocol, selected):
    temperatures, commands, status = signal_columns(protocol)
    cols = (*temperatures, *commands, status)
    windows = {}
    for day, role in selected:
        for part, stamps in expected_ticks(date.fromisoformat(day), protocol).items():
            windows.update({stamp: (role, part) for stamp in stamps})
    rows, annotations = [], []
    if windows:
        for stamp, *values in telemetry(raw, protocol, (*cols, "fault")):
            if stamp not in windows:
                continue
            role, part = windows[stamp]
            row = {"Time": stamp.isoformat(sep=" "), "site": SITE, "ahu": protocol["ahu"],
                   "window_id": role, "event_id": "AHU1_Fault4_schedule15" if role == "event" else "",
                   "partition": part, **{key: val if finite(val) else None for key, val in zip(cols, values[:-1])}}
            rows.append(row)
            annotations.append({"Time": row["Time"], "window_id": role, "partition": part,
                                "publisher_fault_evaluation_only": values[-1]})
        if len(rows) != len(windows):
            raise Stop("STOP_EXTRACTION_GRID")
    return rows, annotations, ["Time", "site", "ahu", "window_id", "event_id", "partition", *cols]


def feasibility(rows, protocol, source_sha):
    temperatures, commands, status = signal_columns(protocol)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["window_id"], row["partition"]].append(row)
    for (window, part), group in grouped.items():
        for key in (*temperatures, *commands, status):
            sequence = [row[key] for row in group]
            values = [v for v in sequence if v is not None]
            kind = ("PUBLISHED_MEASURED_VALUE_INDEPENDENCE_UNATTESTED" if key in temperatures else
                    "BAS_COMMAND" if key in commands else "BAS_STATUS")
            yield {"window_id": window, "partition": part, "native_header": key,
                   "unit": UNITS[key.split("__")[0]], "role": kind, "native_ticks": len(group),
                   "finite": len(values), "missing": len(group) - len(values),
                   "min": min(values) if values else None, "max": max(values) if values else None,
                   "adjacent_command_or_status_changes": (
                       sum(a is not None and b is not None and a != b for a, b in zip(sequence, sequence[1:]))
                       if key not in temperatures else None),
                   "source_sha256": source_sha}


def prepare(raw, folder, output, protocol, manifest):
    signal_columns(protocol)
    events = read_schedule(raw)
    day = date.fromisoformat(protocol["event_date"])
    event = next((e for e in events if e.row == protocol["schedule_row"]), None)
    ticks = expected_ticks(day, protocol)
    if (event is None or (event.ahu, event.fault, event.start, event.end) !=
            (protocol["ahu"], protocol["fault"], ticks["WINDOW"][0], ticks["POST"][0])):
        raise Stop("STOP_PRIMARY_SCHEDULE_MISMATCH")
    start, end, masks = read_masks(raw, protocol)
    days = (start.date() + timedelta(days=i) for i in range((end.date() - start.date()).days + 1))
    candidates = [qualify(other, protocol, events, masks) for other in days
                  if other != day and other.weekday() == day.weekday()]
    primary = qualify(day, protocol, events, masks, primary=True)
    chosen, gate = select(primary, candidates, protocol["negative_controls_max"])
    picked = dict(chosen)
    ranked = sorted(candidates, key=lambda row: (abs(row["relative_weeks"]), row["date"]))
    table(output / "ELIGIBILITY_12.csv",
          [{**primary, "selection": picked.get(primary["date"], "excluded")}, *
           ({**row, "selection": picked.get(row["date"], "eligible_not_selected" if row["eligible"] else "excluded")}
            for row in ranked)])
    table(output / "CONTROLS_12.csv", [{"date": d, "window_id": role, "health": "UNVERIFIED"}
                                      for d, role in chosen if role != "event"], ["date", "window_id", "health"])
    receipt = {
        "status": gate, "causal": "CAUSAL_EFFECT_NOT_IDENTIFIED", "field_fdd": "FIELD_FDD_ACCURACY_NOT_EVALUATED",
        "event_schedule_row": event.row, "event_start_naive": str(event.start), "event_end_exclusive_naive": str(event.end),
        "event_publisher_title_evaluation_only": event.title, "event_publisher_note_evaluation_only": event.note,
        "other_site_dates_evaluated": len(candidates), "eligible_candidates": sum(row["eligible"] for row in candidates),
        "rejected_candidates": sum(not row["eligible"] for row in candidates),
        "rejection_reasons_nonexclusive": dict(Counter(reason for row in candidates if row["reasons"]
                                                      for reason in row["reasons"].split("|"))),
        "clock": protocol["clock"], "selected": picked,
        "selection_sealed_at": datetime.now(TZ).isoformat(),
        "selection_input": "native_time + finite_mask_only + BAS context + publisher schedule exclusions",
        "source_ahu_sha256": manifest["files"][protocol["ahu"] + ".xlsx"]["publisher_sha256"],
    }
    dump(output / "SELECTION_12.json", receipt)
    rows, annotation, fields = extract(raw, protocol, chosen)
    table(output / "RAW_SLICE_12.csv", rows, fields)
    table(output / "PUBLISHER_ANNOTATIONS_12.csv", annotation,
          ["Time", "window_id", "partition", "publisher_fault_evaluation_only"])
    checks = list(feasibility(rows, protocol, receipt["source_ahu_sha256"]))
    table(output / "FEASIBILITY_12.csv", checks, list(checks[0]) if checks else
          ["window_id", "partition", "native_header", "unit", "role", "native_ticks", "finite", "missing",
           "min", "max", "adjacent_command_or_status_changes", "source_sha256"])
    (output / "PREPARED_12.sha256").write_text("".join(f"{digest(output / name)}  {name}\n" for name in PREPARED_FILES))
    print(f"{gate} preparation sealed; {len(candidates)} comparator dates, "
          f"{receipt['eligible_candidates']} eligible, {len(rows)} native selected ticks. No medians computed.")


def calculate(output, protocol):
    observed = dict((name, digest_) for digest_, name in
                    (line.split("  ", 1) for line in (output / "PREPARED_12.sha256").read_text().splitlines()))
    if observed != {name: digest(output / name) for name in PREPARED_FILES}:
        raise Stop("STOP_PREPARATION_SHA_MISMATCH")
    selection = json.loads((output / "SELECTION_12.json").read_text())
    temperatures, _, _ = signal_columns(protocol)
    before, behind, _ = protocol["secondary"]
    values = defaultdict(list)
    with (output / "RAW_SLICE_12.csv").open() as stream:
        for row in csv.DictReader(stream):
            key = row["window_id"], row["partition"]
            for field in temperatures:
                if row[field]:
                    values[*key, field].append(float(row[field]))
            if row[before] and row[behind]:
                values[*key, DIFF].append(float(row[behind]) - float(row[before]))
    result = []
    for day, window in selection["selected"].items():
        for field in (*temperatures, DIFF):
            counts = {part: len(values[window, part, field]) for part in PARTS}
            medians = {part: median(values[window, part, field]) if counts[part] else None for part in PARTS}
            change = medians["WINDOW"] - medians["PRE"] if counts["WINDOW"] and counts["PRE"] else None
            result.append({"window_id": window, "date": day, "channel": field, "unit": "°C",
                           **{f"{part}_n": counts[part] for part in PARTS},
                           **{f"{part}_median": medians[part] for part in PARTS},
                           "window_minus_pre": change})
    table(output / "DESCRIPTIVE_12.csv", result, list(result[0]) if result else
          ["window_id", "date", "channel", "unit", "PRE_n", "WINDOW_n", "POST_n", "PRE_median",
           "WINDOW_median", "POST_median", "window_minus_pre"])
    changes = {row["window_id"]: row["window_minus_pre"] for row in result if row["channel"] == protocol["sat"]}
    effect = changes["event"] - changes["comparison"] if "comparison" in changes else None
    dump(output / "RESULT_12.json", {
        "status": selection["status"], "scope": "EXPLORATORY_REPORTED_SENSOR_ASSOCIATION",
        "causal": selection["causal"], "field_fdd": selection["field_fdd"], "stage11_causal_gate": "STOP",
        "sat_window_minus_pre_C": changes, "event_minus_comparison_change_C": effect,
        "calculated_at": datetime.now(TZ).isoformat(),
    })
    print(selection["status"], "SAT changes", changes, "descriptive event minus comparison", effect)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "calculate"))
    parser.add_argument("raw", type=Path)
    parser.add_argument("protocol_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        protocol = load_protocol(args.protocol_dir)
        manifest = verify_sources(args.raw, args.protocol_dir, protocol)
        if args.step == "prepare":
            prepare(args.raw, args.protocol_dir, args.output, protocol, manifest)
        else:
            calculate(args.output, protocol)
    except Stop as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
