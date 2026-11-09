"""Reproduce the G5.6 header and descriptive nominal receipt from two exposed days."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from statistics import median

DAYS = ("20170714_Baseline.csv", "20170729_Baseline.csv")
COLUMNS = (7, 54, 55, 56, 58, 62, 72, 73)


def audit(source):
    receipt = {}
    for name in DAYS:
        path = source / name
        raw = path.read_bytes()
        reader = csv.reader(raw.decode("latin-1").splitlines())
        header = next(reader)
        triplets = [tuple(Decimal(row[i - 1]) for i in (54, 55, 62)) for row in reader]
        assert triplets and all(value.is_finite() for row in triplets for value in row)
        receipt[name] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "exposure": "EXPLORATORY_EXPOSED",
            "columns_1based": {i: header[i - 1] for i in COLUMNS},
            "rows": len(triplets),
            "between_differs_from_sat": sum(b != s for _, s, b in triplets),
            "between_equals_mat": sum(b == m for m, _, b in triplets),
            "median_between_minus_sat_deg_f": str(median(b - s for _, s, b in triplets)),
            "median_between_minus_mat_deg_f": str(median(b - m for m, _, b in triplets)),
        }
    assert receipt[DAYS[0]]["columns_1based"] == receipt[DAYS[1]]["columns_1based"]
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.source), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
