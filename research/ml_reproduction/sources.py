"""Audit the publisher SD-AHU archive, then prepare a bounded read-only training cache."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ARCHIVE_URL = "https://fdddata.lbl.gov/data/Simulated_LBNL_FDD_Data_Sets_SDAHU/LBNL_FDD_Data_Sets_SDAHU.zip"
BASELINE = "AHU_annual.csv"
BIASES = {f"coi_bias_{n}_annual.csv": n for n in (2, 4, -2, -4)}
CASES = {
    BASELINE: ("healthy", "publisher baseline"),
    **{name: (f"SA {n:+d} C", "inventory sa_bias alias; same OA and TMY required") for name, n in BIASES.items()},
    **{f"damper_stuck_{p:03}_annual.csv": (f"Damper stuck {p}%", "inventory and actuator position") for p in (10, 25, 75)},
    **{f"coi_stuck_{p:03}_annual.csv": (f"Valve stuck {p}%", "inventory and actuator position") for p in (10, 50, 75)},
    "coi_leakage_010_annual.csv": ("Valve leak (unique payload)", "duplicate severity collapsed; exact paper member unspecified"),
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def timestamp(frame):
    return pd.DatetimeIndex(pd.to_datetime(frame["Datetime"], format="%Y-%m-%d %H:%M:%S", errors="raise")).as_unit("ns")


def audit(archive_path, cache, output):
    cache.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    healthy = None
    with ZipFile(archive_path) as archive:
        members = sorted((item for item in archive.infolist() if item.filename.endswith(".csv")),
                         key=lambda item: (Path(item.filename).name != BASELINE, item.filename))
        for item in members:
            name = Path(item.filename).name
            raw = cache / "input.csv"
            with archive.open(item) as src, raw.open("wb") as dst:
                digest = hashlib.sha256()
                while block := src.read(1024 * 1024):
                    digest.update(block)
                    dst.write(block)
            with raw.open() as stream:
                header = next(csv.reader(stream))
            if len(header) != len(set(header)) or header[0] != "Datetime":
                raise ValueError(f"Invalid source header: {name}")
            frame = pd.read_csv(raw, engine="pyarrow")
            raw.unlink()
            times = timestamp(frame)
            frame["Datetime"] = times
            if healthy is None:
                healthy = frame
            equal_clock = times.equals(pd.DatetimeIndex(healthy["Datetime"]))
            numeric = frame.drop(columns="Datetime").to_numpy(dtype=float)
            finite = np.isfinite(numeric)
            same = {}
            if equal_clock:
                for column in ("OA_TEMP", "SYS_CTL", "SF_SPD_DM", "SA_TEMP", "SA_TEMPSPT", "CHWC_VLV_DM", "MA_TEMP"):
                    left = frame[column].to_numpy()
                    right = healthy[column].to_numpy()
                    diff = left - right
                    same[column] = {"equal_rows": int((diff == 0).sum()), "mean_delta": float(diff.mean())}
            role, evidence = CASES.get(name, ("excluded", "outside Table 2 or duplicate/short member"))
            records[name] = {
                "archive_member": item.filename, "sha256": digest.hexdigest(), "crc32": f"{item.CRC:08x}",
                "bytes": item.file_size, "rows": len(frame), "columns": header, "start": str(times[0]), "end": str(times[-1]),
                "duplicate_timestamps": int(times.duplicated().sum()),
                "one_minute_grid": bool((np.diff(times.asi8) == pd.Timedelta(minutes=1).value).all()),
                "same_clock_as_healthy": equal_clock,
                "nonfinite_cells": int((~finite).sum()),
                "nonfinite_by_column": {name: int((~finite[:, index]).sum()) for index, name in enumerate(header[1:])},
                "sys_ctl_counts": {str(key): int(value) for key, value in frame["SYS_CTL"].value_counts().items()},
                "supply_fan_counts": {str(key): int(value) for key, value in frame["SF_SPD_DM"].value_counts().items()},
                "comparison_to_healthy": same,
                "actuator_position": {column: [float(frame[column].min()), float(frame[column].median()), float(frame[column].max())]
                                      for column in ("OA_DMPR", "CHWC_VLV")},
                "paper_role": role, "role_evidence": evidence,
            }
            if name in CASES:
                frame.to_parquet(cache / f"{name}.parquet", index=False, compression="snappy")
            print(f"PASS CRC SHA rows grid: {name} {len(frame)} {digest.hexdigest()}", flush=True)
    for name, row in records.items():
        row["byte_duplicates"] = [other for other, candidate in records.items()
                                  if other != name and row["sha256"] == candidate["sha256"]]
    selected = [records[name] for name in CASES if name in records]
    structural_pass = len(selected) == 12 and len({row["sha256"] for row in selected}) == 12 and all(
        row["rows"] == 525540 and row["same_clock_as_healthy"] and row["one_minute_grid"]
        and len(row["columns"]) == 31 and row["columns"] == selected[0]["columns"] for row in selected
    )
    result = {"url": ARCHIVE_URL, "archive_sha256": sha(archive_path), "structural_pass": structural_pass, "members": records}
    (output / "source-audit.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    fields = ["archive_member", "sha256", "crc32", "rows", "start", "end", "one_minute_grid", "nonfinite_cells",
              "paper_role", "role_evidence", "byte_duplicates"]
    with (output / "SOURCE_IDENTITY_AND_LABELS.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**row, "byte_duplicates": "|".join(row["byte_duplicates"])} for row in records.values())
    (output / "SOURCE_SHA256SUMS.txt").write_text(
        f"{result['archive_sha256']}  LBNL_FDD_Data_Sets_SDAHU.zip\n"
        + "".join(f"{row['sha256']}  {row['archive_member']}\n" for row in records.values()))
    if not structural_pass:
        raise ValueError("STOP_PAPER_REPRO_BY_DATA: full official scenarios not available")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive_path", "cache", "output"):
        parser.add_argument(name, type=Path)
    audit(**vars(parser.parse_args()))
