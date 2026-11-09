"""Preliminary APAR applicability audit. No rule scores or operational integration."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path

from openpyxl import load_workbook

from research.ml_field_observational_12 import replay as source

PINS = {
    "PREREGISTRATION.md": "62b794312b6e6c3f39132ca2b32ce658c58c4920cd37401109a23ee6ec4378ff",
    "PREREGISTRATION.json": "84f8a29451dd87c5a4a28fd023715355eeebd50d757f9d7f46e7387793fb3797",
}
EXPECTED_AHUS = {"AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24"}
EXCLUDED_SETPOINT_ALIASES = (
    "air_temperature__required_value__exahust_air_inlet",
    "air_temperature__min__supply_air_outlet",
    "air_temperature__max__supply_air_outlet",
    "water_temperature__required_value__heater",
)


def preregistration(folder):
    for name, digest in PINS.items():
        if source.digest(folder / name) != digest:
            raise source.Stop("STOP_PREREGISTRATION_SHA_MISMATCH")
    sealed = datetime.fromisoformat((folder / "PREREGISTRATION_CREATED_AT.txt").read_text().strip())
    if sealed.tzinfo is None or sealed >= datetime.now(source.TZ):
        raise source.Stop("STOP_PREREGISTRATION_CLOCK")
    return json.loads((folder / "PREREGISTRATION.json").read_text())


def classify_columns(headers, protocol):
    expected = {protocol["sat"]: "REPORTED_MEASUREMENT",
                protocol["sat_setpoint"]: "ACTIVE_SUPPLY_SETPOINT_CANDIDATE",
                protocol["valve_command"]: "BAS_COMMAND",
                **{key: "BAS_STATUS" if "__real_value__" in key else "BAS_COMMAND"
                   for key in protocol["context"]},
                **dict.fromkeys(EXCLUDED_SETPOINT_ALIASES, "EXCLUDED_AS_SAT_SETPOINT")}
    if protocol["sat_setpoint"] in headers:
        # A later source cannot silently be treated as the preregistered STOP or scored.
        raise source.Stop("STOP_NEW_SETPOINT_HEADER_REQUIRES_SOURCE_REVIEW")
    return [(key, role, key in headers) for key, role in expected.items()]


def compare_reason(day, known_dates, radius):
    reasons = ["NO_ACTIVE_SUPPLY_AIR_SETPOINT", "HEATING_MODE_NOT_ATTESTED", "THRESHOLDS_UNSET"]
    if any(abs((event - day).days) <= radius for event in known_dates):
        reasons.append("SITE_INTERVENTION_DAY_OR_BUFFER")
    return "|".join(reasons)


def audit_unit(path, protocol, known_dates, source_sha):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = iter(book["Sheet1"].values)
        headers = tuple(next(rows))
        if headers.count("Time") != 1 or len(set(headers)) != len(headers):
            raise source.Stop(f"STOP_NATIVE_HEADERS {path.name}")
        channels = classify_columns(set(headers), protocol)
        index = {key: i for i, key in enumerate(headers)}
        tick = timedelta(seconds=protocol["cadence_seconds"])
        metadata = dict(ahu=path.stem, source_sha256=source_sha)
        field_counts = Counter()
        days = {}
        previous = None
        for row in rows:
            stamp = row[index["Time"]]
            if (not isinstance(stamp, datetime) or stamp.tzinfo is not None or stamp.minute % 5
                    or stamp.second or stamp.microsecond or (previous is not None and stamp - previous != tick)):
                raise source.Stop(f"STOP_NATIVE_GRID {path.name}")
            previous = stamp
            day = stamp.date()
            report = days.setdefault(day, {**metadata, "date": str(day), "first_native_tick": str(stamp),
                                           "ticks": 0, "native_context_match_ticks": 0})
            report["end_exclusive_native"] = str(stamp + tick)
            report["ticks"] += 1
            for key, _, present in channels:
                if present and source.finite(row[index[key]]):
                    field_counts[key] += 1
            if all(key in index and row[index[key]] == value for key, value in protocol["context"].items()):
                report["native_context_match_ticks"] += 1
        if sum(item["ticks"] for item in days.values()) != 52705:
            raise source.Stop(f"STOP_NATIVE_COVERAGE {path.name}")
        for day, report in days.items():
            report.update(cadence_seconds=protocol["cadence_seconds"], clock=protocol["clock"],
                          qualified_ticks=0, reasons_for_every_tick=compare_reason(
                              day, known_dates, protocol["date_buffer_days"]))
        return [
            {**metadata, "native_header": key, "role": role, "header_present": present,
             "finite_native_ticks": field_counts[key]} for key, role, present in channels
        ], list(days.values())
    finally:
        book.close()


def run(raw, manuscript, evidence, output):
    protocol = preregistration(evidence)
    manifest = source.verify_sources(raw, evidence, protocol)
    if source.digest(manuscript) != protocol["paper_sha256"]:
        raise source.Stop("STOP_MANUSCRIPT_SHA_MISMATCH")
    events = source.read_schedule(raw)
    known_dates = {event.day for event in events}
    paths = {name for name in manifest["files"] if Path(name).stem in EXPECTED_AHUS}
    if {Path(name).stem for name in paths} != EXPECTED_AHUS or len(manifest["files"]) != 8:
        raise source.Stop("STOP_SOURCE_INVENTORY")
    ledger, fields = [], []
    for name in sorted(paths):
        digest = manifest["files"][name]["publisher_sha256"]
        roles, blocks = audit_unit(raw / name, protocol, known_dates, digest)
        fields.extend(roles)
        ledger.extend(blocks)
    source.table(output / "CHANNEL_ROLES_14.csv", fields)
    source.table(output / "COMPARISON_ELIGIBILITY_14.csv", ledger)
    result = {
        "scope": protocol["scope"], "method": protocol["method"],
        "gate_a": "STOP_NO_ACTIVE_SUPPLY_AIR_SETPOINT",
        "gate_b": "NOT_RUN_GATE_A_STOP",
        "publisher_originals_sha256_verified": len(manifest["files"]),
        "manuscript_sha256_verified": protocol["paper_sha256"],
        "registered_schedule_rows": len(events), "registered_intervention_dates": len(known_dates),
        "site_count": 1, "ahu_count": len(paths), "ledger_blocks": len(ledger),
        "native_ticks": sum(row["ticks"] for row in ledger),
        "native_context_match_ticks": sum(row["native_context_match_ticks"] for row in ledger),
        "site_buffer_ticks": sum(row["ticks"] for row in ledger
                                 if "SITE_INTERVENTION_DAY_OR_BUFFER" in row["reasons_for_every_tick"]),
        "qualified_ticks": 0, "comparisons_computed": 0,
        "thresholds": protocol["thresholds"], "workbook_fault_labels_used": False,
        "stage11_causal_gate": "STOP", "causal_effect_identified": False, "field_fdd_accuracy_evaluated": False,
    }
    source.dump(output / "GATE_RESULT_14.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        run(**vars(args))
    except (source.Stop, OSError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
