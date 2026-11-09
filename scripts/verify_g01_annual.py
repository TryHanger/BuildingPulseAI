"""Verify every derived row and channel against the hash-frozen official annual member."""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

manifest = json.loads(Path("research/g0-g1/DATASET_MANIFEST.json").read_text())
source = next(item for item in manifest["local_slices"] if item.get("is_full_year"))
derivation = source["parquet_derivation"]
raw = Path("data/raw") / source["path"]
processed = Path("data") / derivation["path"]
for path, digest in ((raw, source["sha256"]), (processed, derivation["sha256"])):
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == digest
assert source["sha256"] == next(member["sha256"] for member in manifest["members"]
                                if member["path"] == source["archive_member"])
parquet = pq.ParquetFile(processed)
rows = 0
for index, actual in enumerate(pd.read_csv(
    raw, chunksize=derivation["row_group_rows"], float_precision="round_trip",
)):
    actual["Datetime"] = pd.to_datetime(actual["Datetime"], format="%Y-%m-%d %H:%M:%S")
    matched = parquet.read_row_group(index).to_pandas()
    pd.testing.assert_frame_equal(actual.reset_index(drop=True), matched, check_exact=True)
    rows += len(actual)
assert rows == source["rows"] == parquet.metadata.num_rows
print(f"PASS {rows} rows × {len(parquet.schema_arrow.names)} columns, exact values and source-local timestamps")
