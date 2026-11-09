"""Independent ZIP/XML verification of the reported structural STOP."""
import argparse
from collections import Counter
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path

from research.ml_field_observational_12.oracle import EPOCH, csv_rows, numeric, schedules, sheet

UNITS = ("AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24")


def verify(raw, manuscript, artifacts):
    manifest = json.loads((artifacts / "evidence/SOURCE_PROVENANCE_11.json").read_text())
    assert len(manifest["files"]) == 8
    for name, entry in manifest["files"].items():
        data = (raw / name).read_bytes()
        assert len(data) == entry["bytes"] and sha256(data).hexdigest() == entry["publisher_sha256"]
    assert sha256(manuscript.read_bytes()).hexdigest() == manifest["manuscript_sha256"]
    protocol = json.loads((artifacts / "PREREGISTRATION.json").read_text())
    fields = {(row["ahu"], row["native_header"]): row for row in csv_rows(artifacts / "CHANNEL_ROLES_14.csv")}
    ledger = {(row["ahu"], row["date"]): row for row in csv_rows(artifacts / "COMPARISON_ELIGIBILITY_14.csv")}
    blocked = {day + timedelta(days=shift) for _, _, _, _, day, _, _ in schedules(raw) for shift in (-1, 0, 1)}
    total = 0
    for unit in UNITS:
        rows = iter(sheet(raw / f"{unit}.xlsx"))
        _, header = next(rows)
        mapping = {name: col for col, name in header.items()}
        assert protocol["sat_setpoint"] not in mapping
        declared = {key: v for (ahu, key), v in fields.items() if ahu == unit}
        for key, row in declared.items():
            assert row["header_present"] == str(key in mapping)
        values = Counter()
        counts, contexts = Counter(), Counter()
        first, last = {}, {}
        previous = None
        for _, cells in rows:
            stamp = EPOCH + timedelta(seconds=round(cells[mapping["Time"]] * 86400))
            if previous is not None:
                assert stamp - previous == timedelta(minutes=5)
            previous = stamp
            day = stamp.date()
            first.setdefault(day, stamp)
            last[day] = stamp
            counts[day] += 1
            for key in declared:
                if numeric(cells.get(mapping.get(key))):
                    values[key] += 1
            if all(cells.get(mapping.get(key)) == wanted for key, wanted in protocol["context"].items()):
                contexts[day] += 1
        assert sum(counts.values()) == 52705
        assert {str(day) for day in counts} == {d for ahu, d in ledger if ahu == unit}
        for day, count in counts.items():
            row = ledger[unit, str(day)]
            assert (str(first[day]), str(last[day] + timedelta(minutes=5))) == (
                row["first_native_tick"], row["end_exclusive_native"])
            assert int(row["ticks"]) == count and int(row["native_context_match_ticks"]) == contexts[day]
            assert row["qualified_ticks"] == "0"
            assert "NO_ACTIVE_SUPPLY_AIR_SETPOINT" in row["reasons_for_every_tick"]
            assert ("SITE_INTERVENTION_DAY_OR_BUFFER" in row["reasons_for_every_tick"]) == (day in blocked)
        assert all(int(row["finite_native_ticks"]) == values[key] for key, row in declared.items())
        total += sum(counts.values())
        print(f"PASS {unit} header absence, {sum(counts.values())} native ticks, {len(counts)} ledger rows")
    result = json.loads((artifacts / "GATE_RESULT_14.json").read_text())
    assert result["native_ticks"] == total == 316230
    assert result["qualified_ticks"] == result["comparisons_computed"] == 0
    assert result["gate_b"] == "NOT_RUN_GATE_A_STOP"
    assert result["workbook_fault_labels_used"] is False
    print("PASS complete source and ledger parity; no scoring ran")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("raw", type=Path)
    cli.add_argument("manuscript", type=Path)
    cli.add_argument("artifacts", type=Path)
    verify(**vars(cli.parse_args()))
