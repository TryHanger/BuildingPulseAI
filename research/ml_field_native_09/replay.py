"""Read-only research runner. Schedule/annotations enter only after rule application."""
import argparse
from bisect import bisect_left
from collections import Counter
from contextlib import closing
import csv
from dataclasses import asdict
from datetime import datetime, timedelta
import json
from pathlib import Path

from openpyxl import load_workbook

from research.ml_field_data_08 import inspect_08 as source
from research.ml_field_native_09.rules import (
    CLOCK, LINEAGE, RULE_VERSION, STEP, TAGS, Tick, apply, binary, precontext, summarize,
)

UNITS = ("AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24")
START = datetime(2019, 3, 1)
END = datetime(2019, 8, 31)
PROTOCOL_SHA = "868a685798c42c5a271149b64089aba8d72e0e8ed2d50a91900bfbe5587c5358"
LEDGER_SHA = "1d7acd72ff0ec71e1ae0fbd33c5b0b15e3f0f02942b91a74729e65d4ef4bd8fa"


class Stop(ValueError):
    pass


def verify_clock(previous, current):
    if not isinstance(current, datetime) or current.tzinfo is not None:
        raise Stop("UNKNOWN_CLOCK_INVALID_TIMESTAMP")
    if previous is None:
        return
    delta = current - previous
    if delta <= timedelta(0):
        raise Stop("UNKNOWN_CLOCK_DUPLICATE_OR_REVERSED")
    if delta != STEP:
        raise Stop("UNKNOWN_CLOCK_NOT_NATIVE_300S")


def read_fans(path):
    evidence, annotations = [], {}
    previous = None
    with closing(load_workbook(path, read_only=True, data_only=True)) as workbook:
        rows = iter(workbook["Sheet1"].values)
        header = next(rows)
        if len(header) != len(set(header)) or "Time" not in header:
            raise Stop("UNKNOWN_CLOCK_OR_AMBIGUOUS_HEADER")
        index = {name: i for i, name in enumerate(header)}
        for row in rows:
            if all(value is None for value in row):
                continue
            timestamp = row[index["Time"]]
            verify_clock(previous, timestamp)
            previous = timestamp
            tick = Tick(timestamp, *(binary(row[index[tag]]) if tag in index else None for tag in TAGS))
            evidence.append(apply(tick))
            if "fault" in index:
                annotations[timestamp] = source.normalize_label(row[index["fault"]])
    if len(evidence) != 52705 or evidence[0].tick.time != START or previous != END:
        raise Stop("UNKNOWN_CLOCK_SOURCE_RANGE_OR_ROW_COUNT")
    return evidence, annotations, set(header)


def window_at(times, evidence, start, end):
    if start is None or end is None or end <= start:
        return "UNKNOWN_CLOCK_OPEN_OR_INVALID_INTERVAL", [], []
    if start < times[0] or end > times[-1] + STEP:
        return "UNKNOWN_CLOCK_OUT_OF_GRID", [], []
    left, right = bisect_left(times, start), bisect_left(times, end)
    return "", evidence[max(0, left - 2):left], evidence[left:right]


def excluded_day(day, intervention_days):
    return day in intervention_days or day - timedelta(days=1) in intervention_days


def trace(output, key, raw, pre, rows):
    name = f"traces/{key}.csv"
    path = output / name
    fields = ["partition", "native_time", "supply", "exhaust", "heat_request", "cool_request",
              "supply_evidence", "paired_evidence", "rule_version", "clock", "raw_file", "raw_sha256"]
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        for partition, evidence in (("PRE", pre), ("WINDOW", rows)):
            for row in evidence:
                values = asdict(row.tick)
                writer.writerow([partition, *values.values(), row.supply_state, row.paired_state,
                                 RULE_VERSION, CLOCK, raw["name"], raw["sha"]])
    return name, source.sha(path)


def outcome(output, key, raw, start, end, pre, rows, issue, annotations):
    out = {
        "replay_id": key, "ahu": Path(raw["name"]).stem, "start_naive": start, "end_naive_exclusive": end,
        "clock": CLOCK, "boundary_grid_aligned": all(t is not None and t.minute % 5 == 0 and
                                                    t.second == t.microsecond == 0 for t in (start, end)),
        "status_reason": issue, "lineage": LINEAGE, "physical_fault": "ABSTAIN",
        "rule_version": RULE_VERSION, "raw_file": raw["name"], "raw_sha256": raw["sha"],
        "source_sheet": "Sheet1", "pre_ticks": len(pre), "window_ticks": len(rows),
    }
    for name in ("supply", "exhaust", "heat", "cool"):
        out[name + "_available"] = sum(getattr(row.tick, name) is not None for row in rows)
    pairs = Counter((row.tick.supply, row.tick.exhaust) for row in rows)
    for s, e in ((0, 0), (0, 1), (1, 0), (1, 1)):
        out[f"pair_{s}{e}_ticks"] = pairs[s, e]
    out["both_available"] = sum(pairs[s, e] for s in (0, 1) for e in (0, 1))
    out["warm_request_ticks"] = sum((r.tick.heat, r.tick.cool) == (1, 0) for r in rows)
    for prefix, field in (("A_", "supply_state"), ("B_", "paired_state")):
        summary = summarize(pre, rows, field, start)
        if issue:
            summary["status"] = "UNKNOWN_CLOCK"
        out.update({prefix + name: val for name, val in summary.items()})
    labels = Counter(annotations.get(row.tick.time, "UNKNOWN") for row in rows)
    out["publisher_label_histogram_evaluation_only"] = json.dumps(labels, sort_keys=True)
    out["trace"], out["trace_sha256"] = trace(output, key, raw, pre, rows)
    return out


def read_schedule(path):
    """Fail closed on ambiguous days, without changing the frozen ledger."""
    try:
        events, _, _ = source.read_schedule(path)
    except (TypeError, ValueError, AttributeError) as exc:
        raise Stop("UNKNOWN_CLOCK_UNRESOLVED_SCHEDULE_DAY") from exc
    return events


def run(raw_dir, manuscript, ledger, protocol, output):
    if source.sha(protocol) != PROTOCOL_SHA or source.sha(ledger) != LEDGER_SHA:
        raise Stop("STOP_SOURCE_PROVENANCE:protocol_or_ledger")
    manifest = json.loads(source.MANIFEST.read_text())
    try:
        files = source.qualify_source(raw_dir, manifest)
    except source.QualificationError as exc:
        raise Stop(f"STOP_SOURCE_PROVENANCE:{exc}") from exc
    if not manuscript.is_file() or manuscript.stat().st_size != source.PAPER["bytes"] or source.sha(manuscript) != source.PAPER["sha256"]:
        raise Stop("STOP_SOURCE_PROVENANCE:manuscript")
    with ledger.open(newline="") as stream:
        ledger_by_row = {int(row["schedule_row"]): row for row in csv.DictReader(stream)}
    events = read_schedule(raw_dir / source.SCHEDULE)
    targets = [event for event in events if event["fault_id"] == "Fault 12"]
    if [(e["schedule_row"], e["ahu"]) for e in targets] != list(zip(range(57, 63), UNITS)):
        raise Stop("STOP_SOURCE_PROVENANCE:window_identity")
    site_days = {event["start_naive"].date() for event in events}
    output.mkdir(parents=True, exist_ok=False)
    (output / "traces").mkdir()
    event_rows, controls, screened, roles = [], [], [], []
    for event in targets:
        ahu = event["ahu"]
        name = ahu + ".xlsx"
        raw = {"name": name, "sha": files[name]["verified_sha256"]}
        evidence, labels, headers = read_fans(raw_dir / name)
        times = [row.tick.time for row in evidence]
        start, end = event["start_naive"], event["end_naive"]
        issue, pre, window = window_at(times, evidence, start, end)
        result = outcome(output, f"event-{ahu}", raw, start, end, pre, window, issue, labels)
        old = ledger_by_row[event["schedule_row"]]
        if (old["ahu"], old["start_naive"], old["end_naive"]) != (ahu, str(start), str(end)):
            raise Stop("STOP_SOURCE_PROVENANCE:ledger_window")
        result.update(
            schedule_row=event["schedule_row"], schedule_sha256=files[source.SCHEDULE]["verified_sha256"],
            publisher_id_evaluation_only=event["fault_id"], note_evaluation_only=event["publisher_note"],
            possible_BAS_override="MERVIS_IDE_PUBLISHER_INTERVENTION_POINT_NOT_ATTESTED",
            matching_label_ticks=sum(source.event_label_matches(labels.get(r.tick.time), event) for r in window),
            end_exact_label_evaluation_only=labels.get(end, "NO_EXACT_TICK"),
            same_ahu_other_overlap_rows=" ".join(str(e["schedule_row"]) for e in events if
                e["ahu"] == ahu and e is not event and e["start_naive"] < end and e["end_naive"] > start),
            stage08_exact_label_ticks=int(old["exact_id_or_title_label_rows"]),
        )
        event_rows.append(result)
        for tag, field in zip(TAGS, ("supply", "exhaust", "heat", "cool")):
            roles.append({
                "ahu": ahu, "file": name, "file_id": files[name]["file_id"], "sha256": raw["sha"],
                "sheet": "Sheet1", "header": tag, "present": tag in headers,
                "role": "BAS_REPORTED_STATUS" if field in ("supply", "exhaust") else "BAS_COMMAND",
                "native_unit": "binary logic", "input": True,
                "valid_binary_rows": sum(getattr(row.tick, field) is not None for row in evidence),
                "total_rows": len(evidence), "source_step_seconds": 300, "first_naive": times[0], "last_naive": times[-1],
            })
        for tag, role in (
            ("signal__required_value__fan_fresh_air", "BAS_COMMAND"),
            ("signal__required_value__fan_exahust_air", "BAS_COMMAND"),
            ("fault", "EVALUATION_ANNOTATION"),
        ):
            roles.append({**roles[-1], "header": tag, "present": tag in headers, "role": role,
                          "native_unit": "annotation" if tag == "fault" else "publisher drive signal",
                          "input": False, "valid_binary_rows": None})
        offset = 7
        while end + timedelta(days=offset) <= times[-1] + STEP:
            shift = timedelta(days=offset)
            left, right = start + shift, end + shift
            candidate_issue, candidate_pre, candidate_window = window_at(times, evidence, left, right)
            if excluded_day(left.date(), site_days):
                reason = "EXCLUDED_SITE_INTERVENTION_OR_NEXT_DAY"
            elif issue or precontext(pre, "paired_state") != "TWO_ON":
                reason = "EVENT_PRECONTEXT_NOT_TWO_WARM_PAIRED_ON"
            elif candidate_issue or precontext(candidate_pre, "paired_state") != "TWO_ON":
                reason = "CONTROL_PRECONTEXT_NOT_TWO_WARM_PAIRED_ON"
            else:
                reason = "QUALIFIED_MATCHED_PRECONTEXT"
                controls.append(outcome(output, f"control-{ahu}-{offset:03}", raw, left, right, candidate_pre,
                                        candidate_window, candidate_issue, labels) | {"offset_calendar_days": offset})
            screened.append({"ahu": ahu, "offset_calendar_days": offset, "start_naive": left,
                             "end_naive_exclusive": right, "decision": reason})
            offset += 7
    source.write_csv(output / "EVENT_OUTCOMES.csv", event_rows)
    if controls:
        source.write_csv(output / "CONTROL_OUTCOMES.csv", controls)
    else:
        control_fields = [*event_rows[0]][:list(event_rows[0]).index("schedule_row")] + ["offset_calendar_days"]
        (output / "CONTROL_OUTCOMES.csv").write_text(",".join(control_fields) + "\n")
    source.write_csv(output / "CONTROL_SCREENING.csv", screened)
    source.write_csv(output / "SOURCE_ROLE_AUDIT.csv", roles)
    source.write_json(output / "SOURCE_MANIFEST_09.json", {
        **manifest, "files": files, "manuscript": source.PAPER, "protocol_sha256": PROTOCOL_SHA,
        "stage08_event_ledger_sha256": LEDGER_SHA, "scheduled_site_days": sorted(site_days),
        "site_count": 1, "intervention_event_day_count": 1, "labels_in_rule_inputs": False,
        "rule_version": RULE_VERSION, "event_windows": len(event_rows), "matched_control_windows": len(controls),
        "screened_control_windows": len(screened),
        "decision": ("STOP_NO_BAS_OBSERVABILITY" if all(row["A_status"] != "OBSERVED" for row in event_rows)
                     else "ACCEPT_FIELD_REPLAY_EXPLORATORY" if controls else "STOP_NO_COMPARABLE_CONTROL"),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("raw_dir", "manuscript", "ledger", "protocol", "output"):
        parser.add_argument(name, type=Path)
    try:
        run(**vars(parser.parse_args()))
    except (Stop, OSError) as error:
        parser.exit(2, str(error) + "\n")
