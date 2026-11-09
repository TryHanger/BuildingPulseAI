"""Pre-run header and already-exposed nominal-only checks for G5.7."""
import argparse
import csv
import json
from pathlib import Path
from statistics import median

from research.g57.observe import COIL, GRID, RUNS, SAT, column_positions, project, require_non_alias, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    args = parser.parse_args()
    receipt = {}
    for run, profile, name, sha in RUNS:
        path = args.data_root / f"g36-{profile}" / name
        with path.open(encoding="utf-8-sig", newline="") as file:
            header = next(csv.reader([file.readline()]))
        indexes = column_positions(header)
        receipt[run] = {"sat_column": indexes[SAT] + 1, "coil_column": indexes[COIL] + 1, "header_width": len(header)}
        if run in {"A", "E"}:
            raw = path.read_bytes()
            verify(raw, sha)
            samples, coils = project(raw, profile, GRID[profile])
            require_non_alias(samples, coils)
            delta = [sample["sat_k"] - coil for sample, coil in zip(samples, coils, strict=True)]
            receipt[run]["exposed_nominal_only"] = {
                "ticks": len(delta), "exact_equal": delta.count(0),
                "median_k": median(delta), "min_k": min(delta), "max_k": max(delta),
            }
    print(json.dumps(receipt, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
