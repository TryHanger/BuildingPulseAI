"""Verify the local CSIRO research copies against the publisher's Git LFS pointers."""
import argparse
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

PUBLISHER_COMMIT = "3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6"
SOURCES = {
    "AHU9": ("csiro_ahu9", ("__index_level_0__",)),
    "AHU10": ("csiro_ahu10", ("__index_level_0__",)),
    "fault-experiments": ("csiro_fault_experiments", ("Start Datetime", "End Datetime")),
}


def main():
    parser = argparse.ArgumentParser()
    for argument in ("pointers", "raw", "output"):
        parser.add_argument(argument, type=Path)
    args = parser.parse_args()
    sources = {}
    for member, (local, time_columns) in SOURCES.items():
        pointer = (args.pointers / f"{member}.lfs").read_text().splitlines()
        expected = pointer[1].split("sha256:")[1]
        path = args.raw / f"{local}.parquet"
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        assert sha == expected and path.stat().st_size == int(pointer[2].split()[1])
        parquet = pq.ParquetFile(path)
        boundaries = {}
        for column in time_columns:
            values = [value for value in parquet.read(columns=[column]).column(column).to_pylist() if value is not None]
            boundaries[column] = {"first": str(min(values)), "last": str(max(values))}
        sources[member] = {
            "source_id": f"sha256:{sha}", "sha256": sha, "bytes": path.stat().st_size,
            "rows": parquet.metadata.num_rows, "columns": parquet.schema_arrow.names, "boundaries": boundaries,
            "provenance": "CSIRO_OPERATIONAL_BMS_CONTROLLED_OVERRIDE", "profile": member,
        }
        print(member, sha, parquet.metadata.num_rows, "Git LFS match")
    result = {
        "publisher_commit": PUBLISHER_COMMIT, "status": "NOT_QUALIFIED_FOR_SELECTED_FAULT_TASK",
        "native_provenance": "BMS fault-generation overrides with scheduled intervals; independent travel and reference SAT unverified",
        "sources": sources,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
