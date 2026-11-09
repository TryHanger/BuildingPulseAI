"""Independent reference using Python's ZIP/XML/CSV only, with no replay imports."""
import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

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


def reference_states(values):
    supply, exhaust, heat, cool = values
    direct = {"0": "OFF", "1": "ON"}.get(supply, "INSUFFICIENT_DATA")
    if not all(v in ("0", "1") for v in values):
        return direct, "INSUFFICIENT_DATA"
    if (heat, cool) != ("1", "0"):
        return direct, "NOT_APPLICABLE"
    return direct, direct if supply == exhaust else "DISAGREE"


def check(raw, output):
    with (output / "EVENT_OUTCOMES.csv").open(newline="") as stream:
        selected = [r for r in csv.DictReader(stream) if r["ahu"] in ("AHU1", "AHU2", "AHU23")]
    with (output / "CONTROL_OUTCOMES.csv").open(newline="") as stream:
        selected.extend(list(csv.DictReader(stream))[:2])
    for result in selected:
        start = datetime.fromisoformat(result["start_naive"])
        end = datetime.fromisoformat(result["end_naive_exclusive"])
        lower = start.replace(minute=start.minute // 5 * 5, second=0, microsecond=0)
        first = lower if lower == start else lower + timedelta(minutes=5)
        original = list(sample(raw / result["raw_file"], first - timedelta(minutes=10), end))
        with (output / result["trace"]).open(newline="") as stream:
            trace = list(csv.DictReader(stream))
        expected = [reference_states(v) for _, v in original]
        assert [(str(t), *states) for (t, _), states in zip(original, expected)] == [
            (r["native_time"], r["supply_evidence"], r["paired_evidence"]) for r in trace
        ], result["replay_id"]
        for index, prefix in enumerate(("A_", "B_")):
            series = [pair[index] for pair in expected]
            transitions = [n for n in range(2, len(series) - 1)
                           if series[n - 1:n + 2] == ["ON", "OFF", "OFF"]]
            first_off = str(original[transitions[0]][0]) if series[:2] == ["ON", "ON"] and transitions else ""
            assert result[prefix + "first_off_inclusive"] == first_off
            assert int(result[prefix + "off_ticks"]) == series[2:].count("OFF")
        print("PASS stdlib XLSX-to-evidence", result["replay_id"], len(trace), "ticks including precontext")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    check(**vars(parser.parse_args()))
