"""Cross-check Stage11 timing/availability via ZIP/XML independently of openpyxl."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta
import json
from math import isfinite
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EPOCH = datetime(1899, 12, 30)
CELSIUS = ("air_temperature__", "water_temperature__")


def read_xlsx(path, windows, headers):
    """Return only timestamp bounds and finite-cell counts, never temperature values."""
    with ZipFile(path) as archive:
        shared = ["".join(text.text or "" for text in node.iter(NS + "t"))
                  for node in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        with archive.open("xl/worksheets/sheet1.xml") as worksheet:
            columns = {}
            available = {name: Counter() for name in windows}
            timestamps = {name: [] for name in windows}
            cutoff = max(end for _, end in windows.values())
            for _, element in ET.iterparse(worksheet, events=("end",)):
                if element.tag != NS + "row":
                    continue
                cells = {re.match("[A-Z]+", cell.get("r")).group(): (cell.get("t", "n"), cell.findtext(NS + "v"))
                         for cell in element}
                if element.get("r") == "1":
                    columns = {shared[int(value)]: column for column, (kind, value) in cells.items()
                               if kind == "s" and value is not None}
                    assert not set(columns) & {"air_temperature__real_value__heater_before",
                                               "air_temperature__real_value__heater_behind",
                                               "air_temperature__real_value__chiller_before"}
                else:
                    kind, value = cells[columns["Time"]]
                    assert kind == "n"
                    stamp = EPOCH + timedelta(seconds=round(float(value) * 86400))
                    if stamp >= cutoff:
                        break
                    for name, (start, end) in windows.items():
                        if start <= stamp < end:
                            timestamps[name].append(stamp)
                            for header, column in columns.items():
                                if header in headers:
                                    kind, value = cells.get(column, ("", None))
                                    if kind == "n" and value is not None and isfinite(float(value)):
                                        available[name][header] += 1
                element.clear()
    return timestamps, available


def main(raw, audit):
    data = json.loads(audit.read_text())
    with audit.with_name("SOURCE_MECHANISM_LEDGER.csv").open() as stream:
        headers = {row["native_header"] for row in csv.DictReader(stream) if row["native_header"].startswith(CELSIUS)}
    ahu_rows = {"AHU1": (15, 25), "AHU2": (16, 26), "AHU8": (17, 27),
                "AHU18": (18, 28), "AHU23": (19, 29), "AHU24": (20, 30)}
    for ahu, rows in ahu_rows.items():
        parts = {(row, phase): metadata for row in rows
                 for phase, metadata in data["windows"][str(row)].items()}
        bounds = {key: (datetime.fromisoformat(part["start_inclusive"]), datetime.fromisoformat(part["end_exclusive"]))
                  for key, part in parts.items()}
        timestamps, counts = read_xlsx(raw / f"{ahu}.xlsx", bounds, headers)
        for key, part in parts.items():
            ticks = timestamps[key]
            assert len(ticks) == part["ticks"]
            assert str(ticks[0]) == part["first_native_tick"] and str(ticks[-1]) == part["last_native_tick"]
            assert all((b - a).total_seconds() == 300 for a, b in zip(ticks, ticks[1:]))
            assert counts[key] == {header: n for header, n in part["finite_by_native_header"].items()
                                    if header.startswith(CELSIUS)}
        print(f"PASS XML timestamps and Celsius-field availability {ahu} · rows {rows[0]}/{rows[1]} · no response computed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("audit", type=Path)
    main(**vars(parser.parse_args()))
