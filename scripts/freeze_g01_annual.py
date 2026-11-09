"""Freeze source-clock coverage and an annual Parquet derivation in a disposable copy."""
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from backend.app.services.import_service import parse_timestamps

MANIFEST = Path("research/g0-g1/DATASET_MANIFEST.json")
VERSION = "pandas-round-trip-float64-source-local-v1"
GROUP_ROWS = 2048


def freeze(manifest):
    members = {member["path"]: member for member in manifest["members"]}
    for source in manifest["local_slices"]:
        if not source["exact_archive_prefix"]:
            continue
        raw = Path("data/raw") / source["path"]
        member = members[source["archive_member"]]
        full_member = source["bytes"] == member["bytes"]
        build_index = full_member and raw.name.endswith("_lbnl_AHU_annual.csv")
        first = last = None
        rows = 0
        with raw.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != source["sha256"]:
                raise ValueError(f"Unmatched raw SHA-256 for {raw}")
            stream.seek(0)
            if build_index:
                relative = Path("processed") / f"{raw.stem}.g01.parquet"
                with NamedTemporaryFile(dir=Path("data") / relative.parent, delete=False) as pending:
                    temporary = Path(pending.name)
                writer = None
            try:
                options = {"dtype": {key: "float64" for key in member["columns"] if key != "Datetime"},
                           "float_precision": "round_trip"} if build_index else {"usecols": ["Datetime"]}
                for chunk in pd.read_csv(stream, chunksize=GROUP_ROWS, **options):
                    timestamps = parse_timestamps(chunk["Datetime"])
                    if timestamps.dt.tz is not None or (last is not None and timestamps.iloc[0] <= last):
                        raise ValueError(f"Invalid source-local ordering for {raw}")
                    if first is None:
                        first = timestamps.iloc[0]
                    last = timestamps.iloc[-1]
                    rows += len(chunk)
                    if build_index:
                        chunk["Datetime"] = timestamps
                        table = pa.Table.from_pandas(chunk, preserve_index=False).replace_schema_metadata({
                            b"source_sha256": source["sha256"].encode(), b"derivation": VERSION.encode(),
                        })
                        if writer is None:
                            writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
                        writer.write_table(table)
                if full_member and (rows, first.isoformat(), last.isoformat()) != (
                    member["rows"], member["first"].replace(" ", "T"), member["last"].replace(" ", "T"),
                ):
                    raise ValueError(f"Unmatched member coverage for {raw}")
                if build_index:
                    writer.close()
                    writer = None
                    stream.seek(0)
                    if hashlib.file_digest(stream, "sha256").hexdigest() != source["sha256"]:
                        raise ValueError(f"Raw changed during derivation for {raw}")
                    with temporary.open("rb") as parquet:
                        digest = hashlib.file_digest(parquet, "sha256").hexdigest()
                    temporary.replace(Path("data") / relative)
                    source["parquet_derivation"] = {
                        "path": str(relative), "sha256": digest, "source_sha256": source["sha256"],
                        "format": VERSION, "row_group_rows": GROUP_ROWS,
                        "pandas_version": pd.__version__, "pyarrow_version": pa.__version__,
                    }
            finally:
                if build_index:
                    if writer is not None:
                        writer.close()
                    temporary.unlink(missing_ok=True)
        source.update(first=first.isoformat(), last=last.isoformat(), rows=rows,
                      is_full_year=full_member and member["rows"] == 525540
                      and member["first"] == "2018-01-01 01:00:00"
                      and member["last"] == "2018-12-31 23:59:00")


if __name__ == "__main__":
    manifest = json.loads(MANIFEST.read_text())
    freeze(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
