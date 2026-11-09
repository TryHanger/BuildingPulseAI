"""Independent source replay with ZIP/XML, no production replay imports."""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from math import isclose, isfinite
from pathlib import Path

from research.ml_field_observational_12.oracle import EPOCH, csv_rows, median_manual, schedules, sheet

PARTS = ("PRE", "WINDOW", "POST")
LIMITS = ["CAUSAL_EFFECT_NOT_IDENTIFIED", "FIELD_FDD_ACCURACY_NOT_EVALUATED",
          "SAME_SITE_TWO_DATES", "NOT_INDEPENDENT_BUILDING_VALIDATION"]


def read_book(raw, unit, signals):
    rows = iter(sheet(raw / f"{unit}.xlsx"))
    _, header = next(rows)
    mapping = {field: k for k, field in header.items()}
    assert set(signals) | {"fault", "Time", "equipment"} <= mapping.keys()
    first = last = None
    records = {}
    count = 0
    for _, row in rows:
        stamp = EPOCH + timedelta(seconds=round(row[mapping["Time"]] * 86400))
        assert row[mapping["equipment"]] == unit
        assert stamp.tzinfo is None and stamp.second == 0 and stamp.minute % 5 == 0
        if last:
            assert (stamp - last).total_seconds() == 300
        first = first or stamp
        last = stamp
        count += 1
        if stamp.weekday() == 4:
            records[stamp] = {field: row.get(mapping[field]) for field in (*signals, "fault")}
    assert count == 52705
    return first.date(), last.date(), records


def windows(start, end):
    return {key: [lo + timedelta(minutes=i * 5) for i in range((hi - lo) // timedelta(minutes=5))]
            for key, lo, hi in (
                ("PRE", start - timedelta(minutes=30), start), ("WINDOW", start, end),
                ("POST", end, end + timedelta(minutes=30)))}


def verify_missing_sat(raw, unit, sat, intervals):
    rows = iter(sheet(raw / f"{unit}.xlsx"))
    _, headers = next(rows)
    mapping = {field: column for column, field in headers.items()}
    hits = 0
    for _, cells in rows:
        stamp = EPOCH + timedelta(seconds=round(cells[mapping["Time"]] * 86400))
        if stamp >= max(end for _, end in intervals):
            break
        if any(lo <= stamp < hi for lo, hi in intervals):
            assert not numeric(cells.get(mapping.get(sat))), (unit, stamp)
            hits += 1
    assert hits == 48
    print(f"PASS {unit} excluded: missing reported SAT at all {hits} candidate WINDOW ticks")


def numeric(value):
    return isinstance(value, float) and isfinite(value)


def screen(schedule, source, event, target, expected, sat, context, primary):
    number, _, _, unit, _, _, _ = event
    lo, hi = expected["PRE"][0], expected["POST"][-1] + timedelta(minutes=5)
    conflicts = [str(n) for n, _, _, ahu, _, start, end in schedule
                 if ahu == unit and not (primary and n == number) and start and end and start < hi and lo < end]
    uncertain = [str(n) for n, _, _, ahu, day, start, end in schedule if ahu == unit and day == target
                 and not (primary and n == number) and (start is None or end is None)]
    buffer = {d.isoformat() for _, _, _, _, d, _, _ in schedule if abs((d - target).days) <= 1 and not primary}
    reasons = set()
    for bad, reason in ((conflicts, "AHU_SCHEDULE_OVERLAP"), (uncertain, "AHU_UNBOUNDED_SCHEDULE"),
                        (buffer, "SITE_EVENT_DAY_OR_BUFFER")):
        if bad:
            reasons.add(reason)
    ledger = {"ahu_overlap_rows": "|".join(conflicts), "ahu_unbounded_rows": "|".join(uncertain),
              "site_blocking_dates": "|".join(sorted(buffer))}
    for part, ticks in expected.items():
        present = [source[t] for t in ticks if t in source]
        missing = len(ticks) - len(present)
        bad_sat = sum(not numeric(r[sat]) for r in present)
        mismatch = sum({k: r[k] for k in context} != context for r in present)
        if missing:
            reasons.add("GRID_INCOMPLETE")
        if bad_sat:
            reasons.add("SAT_NOT_FINITE")
        if mismatch and part != "POST":
            reasons.add("COMMAND_CONTEXT_MISMATCH")
        ledger.update({f"{part}_native": str(len(present)), f"{part}_missing_ticks": str(missing),
                       f"{part}_sat_missing": str(bad_sat), f"{part}_context_mismatch": str(mismatch)})
    return reasons, ledger


def compare_mask(row, expected):
    reasons, counts = expected
    assert set(filter(None, row["reasons"].split("|"))) == reasons, row
    assert row["eligible"] == str(not reasons)
    assert all(row[k] == v for k, v in counts.items()), row
    return not reasons


def same(expected, value):
    if expected is None:
        assert value == ""
    else:
        assert isclose(expected, float(value), rel_tol=0, abs_tol=1e-10), (expected, value)


def audit(raw, data):
    manifest = json.loads((data / "evidence/SOURCE_PROVENANCE_11.json").read_text())
    assert len(manifest["files"]) == 8
    for name, record in manifest["files"].items():
        payload = (raw / name).read_bytes()
        assert len(payload) == record["bytes"]
        assert sha256(payload).hexdigest() == record["publisher_sha256"]
    protocol = json.loads((data / "FIELD_REPLICATION_13_PREREG.json").read_text())
    sat = protocol["sat"]
    temperatures = (sat, *protocol["secondary"])
    commands = protocol["commands"]
    status = protocol["status"]
    signals = (*temperatures, *commands, status)
    assert all("__real_value__" in signal for signal in temperatures)
    assert all("__required_value__" in signal for signal in commands)
    assert status == "logic__real_value__fan_fresh_air"
    assert {row[0] for row in protocol["episodes"]} == {18, 19, 20, 25, 28, 29, 30}
    events = schedules(raw)
    indexed = {event[0]: event for event in events}
    ledgers = {int(row["schedule_row"]): row for row in csv_rows(data / "EPISODE_LEDGER_13.csv")}
    assert set(ledgers) == {15, 16, 17, 18, 19, 20, 25, 26, 27, 28, 29, 30}
    assert ledgers[15]["analysis_status"] == "PREVIOUSLY_EXPLORED"
    for number in (16, 17, 26, 27):
        assert ledgers[number]["analysis_status"] == "NOT_EVALUABLE" and ledgers[number]["reasons"] == "MISSING_CHANNELS"
    for unit, pair in (("AHU2", (16, 26)), ("AHU8", (17, 27))):
        assert all(indexed[n][3] == unit for n in pair)
        verify_missing_sat(raw, unit, sat, [indexed[n][-2:] for n in pair])
    candidate_rows = {(int(row["schedule_row"]), row["date"]): row for row in csv_rows(data / "COMPARATOR_ELIGIBILITY_13.csv")}
    rows = csv_rows(data / "RAW_SLICE_13.csv")
    traces = {(row["window_id"], row["Time"]): row for row in rows}
    labels = {(row["window_id"], row["Time"]): row for row in csv_rows(data / "PUBLISHER_ANNOTATIONS_13.csv")}
    feasibility = {(r["window_id"], r["partition"], r["native_header"]): r
                   for r in csv_rows(data / "FEASIBILITY_13.csv")}
    metrics = {(r["window_id"], r["channel"]): r for r in csv_rows(data / "DESCRIPTIVE_EPISODES_13.csv")}
    annotation = {(r["window_id"], r["partition"]): r for r in csv_rows(data / "ANNOTATION_AUDIT_13.csv")}
    assert len(rows) == len(traces) == len(labels)
    if rows:
        assert set(rows[0]) == set(signals) | {"Time", "site", "ahu", "schedule_row", "window_id", "kind", "partition"}
    books = {}
    actual_selection, all_deltas, expected_keys = {}, {}, set()
    expected_candidates = set()
    main_units = {"Fault 4": set(), "Fault 6": set()}
    main_signs = set()
    for n, fault_code, unit, event_date, duration in protocol["episodes"]:
        event = indexed[n]
        _, fault, title, ahu, day, start, end = event
        assert (ahu, str(day), fault, (end - start).total_seconds()) == (unit, event_date, f"Fault {fault_code}", duration * 60)
        assert (ledgers[n]["start_native"], ledgers[n]["end_exclusive_native"]) == (str(start), str(end))
        if unit not in books:
            books[unit] = read_book(raw, unit, signals)
        first, last, source = books[unit]
        refs = windows(start, end)
        assert [len(refs[part]) for part in PARTS] == [6, duration // 5, 6]
        qualifies = compare_mask(ledgers[n], screen(events, source, event, day, refs, sat,
                                                    protocol["required_context"], True))
        if not qualifies:
            assert ledgers[n]["analysis_status"] == "NOT_EVALUABLE"
            continue
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        days = sorted((d for d in days if d.weekday() == day.weekday() and d != day),
                      key=lambda d: (abs((d - day).days), d))
        qualified = []
        for candidate in days:
            key = n, str(candidate)
            expected_candidates.add(key)
            shift = candidate - day
            check = screen(events, source, event, candidate, windows(start + shift, end + shift), sat,
                           protocol["required_context"], False)
            if compare_mask(candidate_rows[key], check):
                qualified.append(candidate)
        comparator = qualified[0] if qualified else None
        assert ledgers[n]["comparison_date"] == (str(comparator) if comparator else "")
        assert [d for d in days if candidate_rows[n, str(d)]["selected"] == "True"] == ([comparator] if comparator else [])
        actual_selection[str(n)] = {str(day): "event", **({str(comparator): "comparison"} if comparator else {})}
        for selected, kind in ((day, "event"), (comparator, "comparison")):
            if selected is None:
                continue
            window = f"row{n}_{kind}"
            shift = selected - day
            expected = windows(start + shift, end + shift)
            per_channel = {field: {} for field in temperatures}
            for part, ticks in expected.items():
                annotations = Counter()
                for tick in ticks:
                    key = window, str(tick)
                    expected_keys.add(key)
                    r = traces[key]
                    assert (r["site"], r["ahu"], r["schedule_row"], r["kind"], r["partition"]) == (
                        "CTU-UCEEB_Bustehrad", unit, str(n), kind, part)
                    for signal in signals:
                        value = source[tick][signal]
                        if numeric(value):
                            assert float(r[signal]) == value
                        else:
                            assert r[signal] == ""
                    label = source[tick]["fault"] or ""
                    assert labels[key]["publisher_fault_evaluation_only"] == label
                    annotations[label] += 1
                a = annotation[window, part]
                assert json.loads(a["label_histogram_evaluation_only"]) == dict(annotations)
                assert int(a["matching_episode_label_ticks"]) == sum(
                    v for k, v in annotations.items() if k.strip().casefold() in {fault.casefold(), title.casefold()})
                for signal in signals:
                    vals = [source[t][signal] for t in ticks]
                    finite = [v for v in vals if numeric(v)]
                    f = feasibility[window, part, signal]
                    assert (int(f["native_ticks"]), int(f["finite"]), int(f["missing"])) == (
                        len(ticks), len(finite), len(ticks) - len(finite))
                    same(min(finite, default=None), f["min"])
                    same(max(finite, default=None), f["max"])
                    if signal in temperatures:
                        assert f["role"] == "PUBLISHED_MEASURED_VALUE_INDEPENDENCE_UNATTESTED" and f["unit"] == "°C"
                        r = metrics[window, signal]
                        med = median_manual(finite)
                        per_channel[signal][part] = med
                        assert int(r[part + "_finite"]) == len(finite)
                        same(med, r[part + "_median"])
                        if signal == sat:
                            center = (len(finite) - 1) / 2
                            slope = 12 * sum((i - center) * y for i, y in enumerate(finite)) / sum(
                                (i - center) ** 2 for i in range(len(finite)))
                            same(slope, r[part + "_SAT_OLS_C_per_hour"])
                    else:
                        assert f["role"] == ("BAS_COMMAND" if signal in commands else "BAS_STATUS")
                        assert int(f["adjacent_command_or_status_changes"]) == sum(
                            numeric(a) and numeric(b) and a != b for a, b in zip(vals, vals[1:]))
            for signal, phases in per_channel.items():
                before, during = phases["PRE"], phases["WINDOW"]
                delta = during - before if before is not None and during is not None else None
                same(delta, metrics[window, signal]["window_minus_pre_C"])
                expected_sign = "" if delta is None else "negative" if delta < 0 else "positive" if delta > 0 else "zero"
                assert metrics[window, signal]["sign"] == expected_sign
                if signal == sat:
                    all_deltas[window] = delta
                    if kind == "event" and duration == 120:
                        main_units[fault].add(unit)
                        main_signs.add(expected_sign)
        print(f"PASS row {n} {unit}, {duration} minutes, comparator {comparator or 'none'}")
    assert set(candidate_rows) == expected_candidates and set(traces) == set(labels) == expected_keys
    selection = json.loads((data / "SELECTION_13.json").read_text())
    assert selection["selected"] == actual_selection
    result = json.loads((data / "RESULT_13.json").read_text())
    assert result["limits"] == LIMITS and result["site_count"] == 1 and len(result["registered_main_dates"]) == 2
    assert result["qualified_main_ahu_by_fault"] == {k: sorted(v) for k, v in main_units.items()}
    assert result["main_signs"] == sorted(main_signs)
    expected_result = ("STOP_INSUFFICIENT_NATIVE_DATA" if min(map(len, main_units.values())) < 2 else
                       "HETEROGENEOUS_OBSERVATIONS" if len(main_signs) > 1 else "DESCRIPTIVE_MULTI_AHU_OBSERVED")
    assert result["status"] == expected_result
    assert {r["window_id"]: r["window_minus_pre_C"] for r in result["sat_results"]} == all_deltas
    print(f"PASS 8 source hashes, 118 schedule rows, {len(candidate_rows)} comparator masks, "
          f"{len(rows)} native rows, {len(rows) * len(signals)} cells, {len(metrics)} metric rows")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("raw", type=Path)
    cli.add_argument("artifacts", type=Path)
    args = cli.parse_args()
    audit(args.raw, args.artifacts)
