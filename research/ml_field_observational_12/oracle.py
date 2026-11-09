"""Independent ZIP/XML parser and descriptive check for every Stage12 row."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import json
from math import isfinite, isclose
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EPOCH = datetime(1899, 12, 30)
DAY = date(2019, 3, 8)
STAGES = ("PRE", "WINDOW", "POST")
WATER_DIFFERENCE = "reported_heater_behind_minus_before"


def sheet(path):
    with ZipFile(path) as archive:
        shared = ["".join(text.text or "" for text in node.iter(NS + "t"))
                  for node in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        with archive.open("xl/worksheets/sheet1.xml") as source:
            for _, row in ET.iterparse(source, events=("end",)):
                if row.tag != NS + "row":
                    continue
                cells = {}
                for cell in row:
                    column = re.match("[A-Z]+", cell.get("r")).group()
                    kind, value = cell.get("t", "n"), cell.findtext(NS + "v")
                    if value is None:
                        continue
                    if kind == "s":
                        cells[column] = shared[int(value)]
                    elif kind in ("n", "b"):
                        cells[column] = float(value)
                yield int(row.get("r")), cells
                row.clear()


def schedules(raw):
    entries = []
    for number, row in sheet(raw / "Faults_schedule_and_description.xlsx"):
        if number == 1 or not row:
            continue
        day = row["D"]
        day = ((EPOCH + timedelta(days=day)).date() if isinstance(day, float)
               else datetime.strptime(day.strip(), "%d.%m.%Y").date())
        times = [datetime.combine(day, time()) + timedelta(seconds=round(row[k] * 86400))
                 if k in row else None for k in "EF"]
        entries.append((number, row["A"], row["B"], row["C"], day, *times))
    assert len(entries) == 118
    assert next(r for r in entries if r[0] == 15) == (
        15, "Fault 4", "Heating valve is closed during heating regime", "AHU1", DAY,
        datetime(2019, 3, 8, 9), datetime(2019, 3, 8, 11))
    return entries


def read_ahu(raw, columns):
    entries = iter(sheet(raw / "AHU1.xlsx"))
    _, header = next(entries)
    col_index = {value: column for column, value in header.items()}
    records = {}
    first = last = None
    for _, row in entries:
        stamp = EPOCH + timedelta(seconds=round(row[col_index["Time"]] * 86400))
        if last is not None:
            assert (stamp - last).total_seconds() == 300
        first = first or stamp
        last = stamp
        if stamp.weekday() == 4 and time(8, 30) <= stamp.time() < time(11, 30):
            records[stamp] = {field: row.get(col_index[field]) for field in columns}
    return first.date(), last.date(), records


def timetable(day):
    origin = datetime.combine(day, time(8, 30))
    return {p: [origin + timedelta(minutes=5 * i) for i in span]
            for p, span in zip(STAGES, (range(6), range(6, 30), range(30, 36)))}


def numeric(x):
    return isinstance(x, float) and isfinite(x)


def screen(day, scheduled, records, primary, sat, context):
    expected = timetable(day)
    start = datetime.combine(day, time(8, 30))
    end = datetime.combine(day, time(11, 30))
    exclusions = set()
    blocked = {d.isoformat() for _, _, _, _, d, _, _ in scheduled if abs((day - d).days) <= 1 and not primary}
    conflicts = [str(n) for n, _, _, ahu, _, lo, hi in scheduled
                 if ahu == "AHU1" and (not primary or n != 15) and lo and hi and lo < end and start < hi]
    incomplete = [str(n) for n, _, _, ahu, d, lo, hi in scheduled
                  if ahu == "AHU1" and d == day and (lo is None or hi is None) and (not primary or n != 15)]
    report = {
        "site_blocking_dates": "|".join(sorted(blocked)), "ahu_overlap_rows": "|".join(conflicts),
        "ahu_unbounded_rows": "|".join(incomplete),
    }
    if blocked:
        exclusions.add("SITE_EVENT_DAY_OR_BUFFER")
    if conflicts:
        exclusions.add("AHU_SCHEDULE_OVERLAP")
    if incomplete:
        exclusions.add("AHU_UNBOUNDED_SCHEDULE")
    for partition, stamps in expected.items():
        present = [records[s] for s in stamps if s in records]
        missing = len(stamps) - len(present)
        sat_missing = sum(not numeric(row[sat]) for row in present)
        context_mismatch = sum({k: row[k] for k in context} != context for row in present)
        if missing:
            exclusions.add("GRID_INCOMPLETE")
        if sat_missing:
            exclusions.add("SAT_NOT_FINITE")
        if context_mismatch and partition != "POST":
            exclusions.add("COMMAND_CONTEXT_MISMATCH")
        report.update({f"{partition}_native": str(len(present)), f"{partition}_missing_ticks": str(missing),
                       f"{partition}_sat_missing": str(sat_missing), f"{partition}_context_mismatch": str(context_mismatch)})
    return exclusions, report


def csv_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def median_manual(values):
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle] + ordered[middle - 1]) / 2


def same(value, serialized):
    if value is None:
        assert serialized == ""
    else:
        assert isclose(value, float(serialized), rel_tol=0, abs_tol=1e-12), (value, serialized)


def main(raw, artifacts):
    provenance = json.loads((artifacts / "evidence/SOURCE_PROVENANCE_11.json").read_text())
    for name, info in provenance["files"].items():
        assert sha256((raw / name).read_bytes()).hexdigest() == info["publisher_sha256"]
    protocol = json.loads((artifacts / "FIELD_OBSERVATIONAL_12_PREREG.json").read_text())
    sat, secondary = protocol["sat"], protocol["secondary"]
    temp = [sat, *secondary]
    columns = [*temp, *protocol["commands"], protocol["status"]]
    context = protocol["required_context"]
    schedule = schedules(raw)
    lo, hi, records = read_ahu(raw, [*columns, "fault"])
    eligible = []
    exclusions = Counter()
    ledger = {date.fromisoformat(row["date"]): row for row in csv_rows(artifacts / "ELIGIBILITY_12.csv")}
    all_days = [lo + timedelta(days=n) for n in range((hi - lo).days + 1) if (lo + timedelta(days=n)).weekday() == 4]
    assert set(ledger) == set(all_days) and len(ledger) == 27
    for day in all_days:
        reasons, mask_counts = screen(day, schedule, records, day == DAY, sat, context)
        assert all(ledger[day][k] == v for k, v in mask_counts.items()), day
        assert set(filter(None, ledger[day]["reasons"].split("|"))) == reasons
        assert ledger[day]["eligible"] == str(not reasons)
        if not reasons and day != DAY:
            eligible.append(day)
        if day != DAY:
            exclusions.update(reasons)
    eligible.sort(key=lambda day: (abs((day - DAY).days), day))
    selected = {str(DAY): "event"}
    if eligible:
        selected[str(eligible[0])] = "comparison"
        selected.update({str(day): f"negative_control_{n}" for n, day in enumerate(eligible[1:4], 1)})
    receipt = json.loads((artifacts / "SELECTION_12.json").read_text())
    assert receipt["selected"] == selected
    assert receipt["other_site_dates_evaluated"] == len(all_days) - 1
    assert receipt["eligible_candidates"] == len(eligible)
    assert receipt["rejected_candidates"] == len(all_days) - 1 - len(eligible)
    assert receipt["rejection_reasons_nonexclusive"] == dict(exclusions)
    assert csv_rows(artifacts / "CONTROLS_12.csv") == [
        {"date": day, "window_id": label, "health": "UNVERIFIED"} for day, label in selected.items() if label != "event"]

    traces = csv_rows(artifacts / "RAW_SLICE_12.csv")
    labels = csv_rows(artifacts / "PUBLISHER_ANNOTATIONS_12.csv")
    assert set(traces[0]) == set(columns) | {"Time", "site", "ahu", "window_id", "event_id", "partition"}
    assert all("fault" not in key and "schedule" not in key for key in traces[0])
    archived = {(row["window_id"], row["Time"]): row for row in traces}
    publisher = {(row["window_id"], row["Time"]): row for row in labels}
    assert len(archived) == len(traces) == len(publisher) == len(labels) == len(selected) * 36
    metrics = {(row["window_id"], row["channel"]): row for row in csv_rows(artifacts / "DESCRIPTIVE_12.csv")}
    checks = {(row["window_id"], row["partition"], row["native_header"]): row
              for row in csv_rows(artifacts / "FEASIBILITY_12.csv")}
    changes = {}
    for day, label in selected.items():
        reference = {part: [records[stamp] for stamp in stamps]
                     for part, stamps in timetable(date.fromisoformat(day)).items()}
        for part, stamps in timetable(date.fromisoformat(day)).items():
            for stamp in stamps:
                key = label, str(stamp)
                row = archived[key]
                assert row["partition"] == publisher[key]["partition"] == part
                assert row["site"] == "CTU-UCEEB_Bustehrad" and row["ahu"] == "AHU1"
                assert row["event_id"] == ("AHU1_Fault4_schedule15" if label == "event" else "")
                for column in columns:
                    actual = records[stamp][column]
                    if numeric(actual):
                        assert float(row[column]) == actual, (key, column)
                    else:
                        assert row[column] == "", (key, column)
                assert publisher[key]["publisher_fault_evaluation_only"] == (records[stamp]["fault"] or "")
            for column in columns:
                audit = checks[label, part, column]
                series = [r[column] for r in reference[part]]
                vals = [v for v in series if numeric(v)]
                assert int(audit["native_ticks"]) == len(stamps)
                assert int(audit["finite"]) == len(vals)
                assert int(audit["missing"]) == len(stamps) - len(vals)
                same(min(vals, default=None), audit["min"])
                same(max(vals, default=None), audit["max"])
                if column not in temp:
                    assert int(audit["adjacent_command_or_status_changes"]) == sum(
                        numeric(a) and numeric(b) and a != b for a, b in zip(series, series[1:]))
        for field in [*temp, WATER_DIFFERENCE]:
            result = metrics[label, field]
            medians = {}
            for part in STAGES:
                if field == WATER_DIFFERENCE:
                    before, behind = secondary[:2]
                    vals = [row[behind] - row[before] for row in reference[part]
                            if numeric(row[behind]) and numeric(row[before])]
                else:
                    vals = [row[field] for row in reference[part] if numeric(row[field])]
                assert len(vals) == int(result[part + "_n"])
                medians[part] = median_manual(vals)
                same(medians[part], result[part + "_median"])
            change = medians["WINDOW"] - medians["PRE"]
            same(change, result["window_minus_pre"])
            if field == sat:
                changes[label] = change
    summary = json.loads((artifacts / "RESULT_12.json").read_text())
    assert summary["sat_window_minus_pre_C"] == changes
    expected_contrast = changes["event"] - changes["comparison"] if eligible else None
    assert summary["event_minus_comparison_change_C"] == expected_contrast
    assert summary["causal"] == "CAUSAL_EFFECT_NOT_IDENTIFIED"
    assert summary["field_fdd"] == "FIELD_FDD_ACCURACY_NOT_EVALUATED"
    print(f"PASS 8 V1 SHA, 118 schedule rows, {len(ledger)} day masks, ranks and controls")
    print(f"PASS {len(traces)} exact native rows, {len(traces) * len(columns)} numeric cells, "
          f"{len(checks)} feasibility records and {len(metrics)} independently recomputed metric rows")
    print("PASS publisher annotations checked in a separate table; omitted from eligibility and numerical columns")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("artifacts", type=Path)
    main(**vars(parser.parse_args()))
