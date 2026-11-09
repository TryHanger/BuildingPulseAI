"""Independently prove the descriptive audit uses only allowed data and ZIP members."""
import argparse
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

from research.ml_domain_shift_07 import audit_07

ALLOWED_MEMBERS = {
    "TRANSFER_05_PROTOCOL.json", "source_fit/SOURCE_FIT_RECEIPT.json", "HISTORICAL_FREEZE_RECEIPT.json",
    "TARGET_NORMAL_06_RECEIPT.json", "MANIFEST.json", "TARGET_NORMAL_06_BLOCKS.csv",
    "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz",
}


def main(source, design_archive, normal_archive, output):
    allowed_paths = {path.resolve() for path in (source, design_archive, normal_archive)}
    opened_members = []
    archive_open = ZipFile.open

    def checked_archive_open(self, name, *args, **kwargs):
        if name not in ALLOWED_MEMBERS:
            raise PermissionError(f"Unapproved archive member: {name}")
        opened_members.append(name)
        return archive_open(self, name, *args, **kwargs)

    def open_guard(event, args):
        if event == "import" and args[0].split(".")[0] in {"lightgbm", "sklearn", "joblib"}:
            raise PermissionError("ML import forbidden in descriptive audit")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.suffix in {".csv", ".parquet", ".zip", ".joblib", ".pkl", ".db"} and path not in allowed_paths:
                raise PermissionError(f"Unapproved data open: {path}")
            if path.name in {"REDUCED_SAT.lightgbm.txt", "REDUCED_SAT_RIDGE.json"}:
                raise PermissionError(f"Unapproved model open: {path}")

    ZipFile.open = checked_archive_open
    sys.addaudithook(open_guard)
    try:
        audit_07.main(source, design_archive, normal_archive, output)
    finally:
        ZipFile.open = archive_open
    print(json.dumps({"target_raw_opened": False, "model_member_opened": False, "prediction_calls": 0,
                      "permitted_archive_members_read": opened_members}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "design_archive", "normal_archive", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
