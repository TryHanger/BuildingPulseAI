"""Independent stdlib oracle for Stage09 CSVs, source workbooks and Stage10 HTTP.

The reference state and summary functions come from the independent Stage09
audit. No imports from the Stage09 replay or Stage10 packager/application.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from urllib.request import urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

def ref_state(s,e,h,c):
    if s not in (0,1): return 'INSUFFICIENT_DATA','INSUFFICIENT_DATA'
    a='ON' if s==1 else 'OFF'
    if any(x not in (0,1) for x in (e,h,c)): return a,'INSUFFICIENT_DATA'
    if (h,c)!=(1,0): return a,'NOT_APPLICABLE'
    return a,a if s==e else 'DISAGREE'

def ref_summ(pre, window, attr, start):
    v=[x[attr] for x in window]; before=[x[attr] for x in pre]
    baseline='INSUFFICIENT_DATA' if len(before)<2 or 'INSUFFICIENT_DATA' in before else 'TWO_ON' if before==['ON','ON'] else 'TWO_OFF' if before==['OFF','OFF'] else 'NOT_APPLICABLE'
    good={'ON','OFF','DISAGREE'}
    status='OBSERVED' if any(a in good and b in good for a,b in zip(v,v[1:])) else 'INSUFFICIENT_DATA'
    if v and set(v)=={'NOT_APPLICABLE'}: status='NOT_APPLICABLE'
    change='ABSTAIN' if status!='OBSERVED' or baseline!='TWO_ON' else 'NO_OBSERVED_CHANGE'
    longest=run=0
    for x in v:
        run=run+1 if x=='OFF' else 0
        longest=max(longest,run)
    first=confirm=last=None
    if change=='NO_OBSERVED_CHANGE':
        lastval=before[-1]
        for j,x in enumerate(v[:-1]):
            if (lastval,x,v[j+1])==('ON','OFF','OFF'):
                first=window[j]['time']; confirm=window[j+1]['time']; last=first-timedelta(minutes=5)
                change='BAS_ON_TO_OFF_OBSERVED';break
            lastval=x
    return {
        'status':status,'baseline':baseline,'change':change,
        'off_ticks':v.count('OFF'), 'known_ticks':sum(x in good for x in v),
        'longest_off_sample_span_seconds': (longest-1)*300 if longest else '',
        'last_on_exclusive':last, 'first_off_inclusive':first, 'confirm_off':confirm,
        'first_off_from_log_start_seconds':int((first-start).total_seconds()) if first else '',
        'confirm_from_log_start_seconds':int((confirm-start).total_seconds()) if confirm else '',
    }

def normalize(v): return '' if v in (None,'') else str(v)

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EPOCH = datetime(1899, 12, 30)
NAMES = ("Time", "logic__real_value__fan_fresh_air", "logic__real_value__fan_exahust_air",
         "logic__required_value__heater", "logic__required_value__chiller")


def sample(path, start, end):
    with ZipFile(path) as archive:
        shared = ["".join(n.text or "" for n in s.iter(NS + "t"))
                  for s in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        with archive.open("xl/worksheets/sheet1.xml") as content:
            for _, row in ET.iterparse(content, events=("end",)):
                if row.tag != NS + "row":
                    continue
                cells = {re.match("[A-Z]+", c.attrib["r"]).group(): c.findtext(NS + "v") for c in row}
                if row.attrib["r"] == "1":
                    columns = {shared[int(i)]: col for col, i in cells.items() if i is not None}
                else:
                    timestamp = EPOCH + timedelta(seconds=round(float(cells[columns["Time"]]) * 86400))
                    if timestamp >= end:
                        break
                    if timestamp >= start:
                        yield timestamp, tuple(cells.get(columns.get(name)) for name in NAMES[1:])
                row.clear()


SIGNALS = ("supply", "exhaust", "heat_request", "cool_request")
AHUS = {"AHU1", "AHU2", "AHU8", "AHU18", "AHU23", "AHU24"}
EXPECTED_CHANGES = {
    "AHU1": ("BAS_ON_TO_OFF_OBSERVED", "BAS_ON_TO_OFF_OBSERVED"),
    "AHU18": ("BAS_ON_TO_OFF_OBSERVED", "BAS_ON_TO_OFF_OBSERVED"),
    "AHU23": ("BAS_ON_TO_OFF_OBSERVED", "NO_OBSERVED_CHANGE"),
    "AHU24": ("BAS_ON_TO_OFF_OBSERVED", "ABSTAIN"),
    "AHU2": ("ABSTAIN", "ABSTAIN"),
    "AHU8": ("ABSTAIN", "ABSTAIN"),
}
EXPECTED_CONTROLS = {f"control-{ahu}-{offset}" for ahu in ("AHU1", "AHU18", "AHU23") for offset in ("063", "077")}


def read_stage09(path):
    """Read CSV rows and verify the independent upstream byte identities."""
    with ZipFile(path) as archive:
        checksums = [line.split("  ", 1) for line in archive.read("SHA256SUMS").decode().splitlines()]
        assert len(checksums) == 49
        assert {name.removeprefix("./") for _, name in checksums} == set(archive.namelist()) - {"SHA256SUMS"}
        for digest, name in checksums:
            assert sha256(archive.read(name.removeprefix("./"))).hexdigest() == digest, name

        def rows(name):
            return list(csv.DictReader(StringIO(archive.read("observed/" + name).decode(), newline="")))

        manifest_bytes = archive.read("observed/SOURCE_MANIFEST_09.json")
        manifest = json.loads(manifest_bytes)
        expected = {}
        for table in ("EVENT_OUTCOMES.csv", "CONTROL_OUTCOMES.csv"):
            for row in rows(table):
                assert row["replay_id"] not in expected
                assert sha256(archive.read("observed/" + row["trace"])).hexdigest() == row["trace_sha256"]
                expected[row["replay_id"]] = (row, rows(row["trace"]))
        assert set(expected) == {f"event-{ahu}" for ahu in AHUS} | EXPECTED_CONTROLS
        return expected, manifest, sha256(manifest_bytes).hexdigest()


def verify(path, response, raw=None):
    expected, manifest, manifest_sha = read_stage09(path)
    provenance = response["provenance"]
    assert provenance["source_manifest_sha256"] == manifest_sha
    assert provenance["stage09_zip_sha256"] == sha256(path.read_bytes()).hexdigest()
    assert provenance["dataset_doi"] == "10.17632/jkw85sm4v4.1"
    assert provenance["version"] == 1 and provenance["cadence_seconds"] == 300
    assert provenance["rule_version"] == "bas-fan-observation@1.0.0"
    assert provenance["clock"] == "UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S"
    assert tuple(provenance["input_columns"][key] for key in SIGNALS) == NAMES[1:]
    assert provenance["timestamp_column"] == NAMES[0]
    assert provenance["files"].keys() == manifest["files"].keys()
    for name, record in provenance["files"].items():
        assert record == {key: manifest["files"][name][key]
                          for key in ("file_id", "bytes", "publisher_sha256", "verified_sha256")}
        assert record["publisher_sha256"] == record["verified_sha256"]
        if raw and name.endswith(".xlsx"):
            assert sha256((raw / name).read_bytes()).hexdigest() == record["publisher_sha256"]

    assert len(response["cases"]) == len(expected)
    assert {case["id"] for case in response["cases"]} == expected.keys()
    for case in response["cases"]:
        outcome, ticks = expected[case["id"]]
        reported = case["archived_outcome"]
        annotations = case["evaluation_metadata"]
        assert reported.keys().isdisjoint(annotations)
        assert reported | annotations == outcome
        assert all("_evaluation_only" not in key and "schedule" not in key for key in reported)
        assert "publisher_label_histogram_evaluation_only" in annotations
        assert case["ahu"] == outcome["ahu"]
        assert case["start"] == outcome["start_naive"]
        assert case["end_exclusive"] == outcome["end_naive_exclusive"]
        start, end = map(datetime.fromisoformat, (case["start"], case["end_exclusive"]))
        assert start.tzinfo is end.tzinfo is None
        assert (end - start).total_seconds() == 5400
        assert len(case["observations"]) == len(ticks) == 20
        reconstructed = []
        for observation, tick in zip(case["observations"], ticks):
            timestamp = datetime.fromisoformat(tick["native_time"])
            assert timestamp.tzinfo is None and timestamp.second == 0 and timestamp.minute % 5 == 0
            relative = int((timestamp - start).total_seconds())
            values = tuple(int(tick[key]) if tick[key] else None for key in SIGNALS)
            direct, paired = ref_state(*values)
            assert (direct, paired) == (tick["supply_evidence"], tick["paired_evidence"])
            assert observation == {**tick, **dict(zip(SIGNALS, values)), "relative_seconds": relative}
            assert observation["clock"] == provenance["clock"]
            assert observation["rule_version"] == provenance["rule_version"]
            assert observation["raw_file"] == outcome["raw_file"]
            assert observation["raw_sha256"] == outcome["raw_sha256"] == provenance["files"][outcome["raw_file"]]["publisher_sha256"]
            reconstructed.append({"time": timestamp, "a": direct, "b": paired, "values": values})
        assert [tick["partition"] for tick in ticks] == ["PRE"] * 2 + ["WINDOW"] * 18
        assert all((v["time"] - u["time"]).total_seconds() == 300
                   for u, v in zip(reconstructed, reconstructed[1:]))
        pre, window = reconstructed[:2], reconstructed[2:]
        assert pre[-1]["time"] < start <= window[0]["time"]
        assert window[-1]["time"] < end <= window[-1]["time"] + timedelta(seconds=300)
        for prefix, attr in (("A_", "a"), ("B_", "b")):
            for key, value in ref_summ(pre, window, attr, start).items():
                assert reported[prefix + key] == normalize(value), (case["id"], prefix, key)
        counts = Counter(r["values"][:2] for r in window)
        for a in (0, 1):
            for b in (0, 1):
                assert int(reported[f"pair_{a}{b}_ticks"]) == counts[a, b]
        for idx, key in enumerate(("supply_available", "exhaust_available", "heat_available", "cool_available")):
            assert int(reported[key]) == sum(r["values"][idx] is not None for r in window)
        assert int(reported["both_available"]) == sum(counts[a, b] for a in (0, 1) for b in (0, 1))
        assert int(reported["warm_request_ticks"]) == sum(r["values"][2:] == (1, 0) for r in window)
        changes = (reported["A_change"], reported["B_change"])
        if case["id"] in EXPECTED_CONTROLS:
            assert case["kind"] == "matched_control"
            assert changes == ("NO_OBSERVED_CHANGE",) * 2 and counts[1, 1] == 18
        else:
            assert case["kind"] == "intervention"
            assert changes == EXPECTED_CHANGES[case["ahu"]]
            assert annotations["publisher_id_evaluation_only"] == "Fault 12"
        if raw:
            observed = list(sample(raw / outcome["raw_file"], reconstructed[0]["time"], end))
            assert observed == [(r["time"], tuple(None if x is None else str(x) for x in r["values"]))
                                for r in reconstructed], case["id"]
        print(f"PASS {case['id']} · 20 CSV ticks, every saved field, independent A/B"
              + (", original XLSX ticks and four inputs" if raw else ""))
    print("PASS 49 archive entries, 12 traces, 240 ticks, 384 independently recomputed fields")
    print("PASS raw XLSX for 12/12 windows" if raw else "Raw XLSX comparison omitted (no --raw supplied)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage09", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", type=Path)
    source.add_argument("--url")
    parser.add_argument("--raw", type=Path)
    args = parser.parse_args()
    if args.bundle:
        content = args.bundle.read_bytes()
    else:
        with urlopen(args.url, timeout=30) as stream:
            content = stream.read()
    verify(args.stage09, json.loads(content), args.raw)
