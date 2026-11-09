"""Read source metadata and cadence for feasibility. No prediction or fitting."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path

import numpy as np
from pyarrow.parquet import ParquetFile

from research.ml_validation_04.evidence import sha


def csv_clock(path, g36):
    with path.open(encoding="utf-8-sig" if g36 else "cp1252", newline="") as stream:
        reader = csv.reader(stream)
        fields = next(reader)
        if g36:
            times = [float(row[0]) for row in reader if row]
        else:
            epoch = datetime(1970, 1, 1)
            dates = [datetime.strptime(f"{row[0].strip()}{int(row[1]):04}", "%Y%m%d%H%M") for row in reader if row]
            times = [(date - epoch).total_seconds() for date in dates]
    return {"sha256": sha(path), "headers": fields, "rows": len(times),
            "interval_seconds_counts": dict(Counter(map(int, np.diff(times))))}


def csiro_clock(path, unit):
    parquet = ParquetFile(path)
    header = parquet.schema_arrow.names
    mat, sat = (f"AHU{unit}ahu{key}Temp" for key in ("Ma", "Sa"))
    time = "__index_level_0__"
    table = parquet.read(columns=[mat, sat, time])
    index = table[time].to_numpy().astype("datetime64[s]").astype("int64")
    mat_values, sat_values = table[mat].to_numpy(), table[sat].to_numpy()
    finite = np.isfinite(mat_values) & np.isfinite(sat_values)
    return {"sha256": sha(path), "headers": header, "rows": len(index),
            "interval_seconds_counts": dict(Counter(map(int, np.diff(index))).most_common(8)),
            "mat_sat_finite_pairs": int(finite.sum()),
            "mat_sat_max_absolute_difference_c": float(np.abs(mat_values[finite] - sat_values[finite]).max())}


def main(data, output):
    csv_files = ["g36-1wk/BaselineSystem.csv", "g36-1wk/CooCoiValStuck_0.csv",
                 "g36-5wk/BaselineSystem.csv", "g36-5wk/CooCoiValStuck_0.csv",
                 "raw/rbc_nesbitt/20170714_Baseline.csv", "raw/rbc_nesbitt/20170811_CooCoiValStuck_100.csv"]
    sources = {name: csv_clock(data / name, name.startswith("g36-")) for name in csv_files}
    for unit in (9, 10):
        name = f"raw/csiro_ahu{unit}.parquet"
        sources[name] = csiro_clock(data / name, unit)
    experiment = data / "raw/csiro_fault_experiments.parquet"
    sources["raw/csiro_fault_experiments.parquet"] = {
        "sha256": sha(experiment), "headers": ParquetFile(experiment).schema_arrow.names,
    }
    with output.open("x") as stream:
        json.dump({"source_prediction_executed": False, "files": sources}, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
