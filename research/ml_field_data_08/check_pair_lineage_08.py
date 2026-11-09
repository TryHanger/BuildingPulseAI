"""Compare the only populated physical/control channels shared by AHU2 and AHU8."""
import argparse
from contextlib import closing
import json
from pathlib import Path

from openpyxl import load_workbook

from research.ml_field_data_08.inspect_08 import MANIFEST, qualify_source, write_json

CHANNELS = ("water_temperature__real_value__heater_before", "logic__required_value__chiller_pump")


def main(raw, output):
    qualify_source(raw, json.loads(MANIFEST.read_text()))
    metrics = {key: dict(ticks=0, missing_both=0, equal_nonmissing=0, different=0) for key in CHANNELS}
    with closing(load_workbook(raw / "AHU2.xlsx", read_only=True, data_only=True)) as left, closing(
        load_workbook(raw / "AHU8.xlsx", read_only=True, data_only=True)
    ) as right:
        streams = iter(left["Sheet1"].values), iter(right["Sheet1"].values)
        headers = tuple(next(stream) for stream in streams)
        indices = {name: tuple(header.index(name) for header in headers) for name in ("Time", *CHANNELS)}
        for a, b in zip(*streams, strict=True):
            i, j = indices["Time"]
            if a[i] != b[j]:
                raise ValueError("AHU2 and AHU8 clocks differ")
            for key in CHANNELS:
                i, j = indices[key]
                x, y = a[i], b[j]
                row = metrics[key]
                row["ticks"] += 1
                row["missing_both"] += x is None and y is None
                row["equal_nonmissing"] += x is not None and x == y
                row["different"] += x != y
    write_json(output, {"units": ["AHU2", "AHU8"], "channel_comparison": metrics,
                        "physical_provenance": "UNVERIFIED_SHARED_OR_DUPLICATED; NO INDEPENDENT CHANNEL CLAIM"})
    print("PASS AHU2/AHU8 available-channel comparison")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
