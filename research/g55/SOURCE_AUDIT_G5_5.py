"""Inspect source headers and nominal sensor availability, without scoring."""
import argparse
import csv
import json
from pathlib import Path
from zipfile import ZipFile

import pyarrow.parquet as pq

G36_COLUMNS = (47, 48, 49, 50, 51, 52, 53, 54, 60, 64, 65, 66, 67, 69, 94, 112)
RBC_FILES = (
    "20170714_Baseline.csv", "20170729_Baseline.csv", "20170811_CooCoiValStuck_100.csv",
    "20170718_OADamStuck_100.csv", "20180711_CooCoiValStuck_80.csv",
    "holdout/20180709_TSup_m3.5.csv",
)
RBC_COLUMNS = (3, 7, 53, 54, 55, 56, 58, 62, 63, 64, 72, 73)
G36_ARCHIVES = (
    ("BUILDINGPULSE_G5_2_G36_SOURCE_BYTES.zip", (
        "g36-5wk/BaselineSystem.csv", "g36-5wk/CooCoiValStuck_0.csv",
        "g36-5wk/OADamStuck_100.csv", "g36-5wk/SupDucLea_20.csv",
        "g36-1wk-probe/CooCoiValStuck_0.csv")),
    ("BUILDINGPULSE_G5_3_G36_1WK_SOURCE_BYTES.zip", ("g36-1wk/CoolingSeason/BaselineSystem.csv",)),
)


def selected(header, positions):
    return {str(i): header[i - 1] for i in positions}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.source_root
    raw = root / "data/raw"
    results = {"scope": "SCHEMA_AND_NOMINAL_AVAILABILITY_ONLY", "g36": {}, "rbc_nesbitt": {}, "csiro": {}}
    for archive, members in G36_ARCHIVES:
        archive_path = root / archive
        with ZipFile(archive_path) as zipped:
            for member in members:
                with zipped.open(member) as stream:
                    header = next(csv.reader([stream.readline().decode("utf-8-sig")]))
                results["g36"][member] = {
                    "archive": archive, "column_count": len(header), "selected_columns_1based": selected(header, G36_COLUMNS),
                }
    g36 = [item["selected_columns_1based"] for item in results["g36"].values()]
    assert len(g36) == 6 and all(item == g36[0] for item in g36)
    lbnl = raw / "ds_8e5b1ddfdd14_lbnl_AHU_annual.csv"
    with lbnl.open(encoding="utf-8-sig") as stream:
        results["lbnl"] = {"file": lbnl.name, "columns": next(csv.reader(stream))}
    for name in RBC_FILES:
        with (raw / "rbc_nesbitt" / name).open(encoding="latin-1", newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            item = {"column_count": len(header), "selected_columns_1based": selected(header, RBC_COLUMNS)}
            if "_Baseline.csv" in name:
                pairs = [(r[53].strip(), r[61].strip(), r[54].strip()) for r in reader if len(r) > 61]
                valid = [tuple(map(float, row)) for row in pairs if all(row)]
                item["nominal_availability"] = {
                    "rows": len(pairs), "numeric_triplets": len(valid), "between_equals_sat": sum(b == s for _, b, s in valid),
                    "distinct_between_coil_values": len({b for _, b, _ in valid}),
                }
            results["rbc_nesbitt"][name] = item
    for name in ("csiro_ahu9.parquet", "csiro_ahu10.parquet"):
        results["csiro"][name] = pq.read_schema(raw / name).names
    results["csiro"]["csiro_fault_experiments.parquet"] = pq.read_schema(raw / "csiro_fault_experiments.parquet").names
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
