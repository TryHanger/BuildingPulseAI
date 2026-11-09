"""Package the accepted Stage09 bytes without running its replay or rules."""
import argparse
import csv
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from zipfile import ZipFile

STAGE09_SHA = "e06ba4b8e837b2bd47d49f3bcd8b7f2dc7fb56eb187a51d038b394a348815db8"
COLUMNS = {
    "supply": "logic__real_value__fan_fresh_air",
    "exhaust": "logic__real_value__fan_exahust_air",
    "heat_request": "logic__required_value__heater",
    "cool_request": "logic__required_value__chiller",
}
EVALUATION_FIELDS = {
    "publisher_label_histogram_evaluation_only", "schedule_row", "schedule_sha256",
    "publisher_id_evaluation_only", "note_evaluation_only", "possible_BAS_override",
    "matching_label_ticks", "end_exact_label_evaluation_only", "same_ahu_other_overlap_rows",
    "stage08_exact_label_ticks", "offset_calendar_days",
}


def freeze(path: Path) -> bytes:
    if sha256(path.read_bytes()).hexdigest() != STAGE09_SHA:
        raise ValueError("Expected the accepted Stage09 review ZIP")
    with ZipFile(path) as archive:
        hashes = {name.removeprefix("./"): digest for digest, name in
                  (line.split("  ", 1) for line in archive.read("SHA256SUMS").decode().splitlines())}
        if len(hashes) != 49 or not all(sha256(archive.read(name)).hexdigest() == digest for name, digest in hashes.items()):
            raise ValueError("Stage09 payload hash mismatch")

        def rows(name):
            return csv.DictReader(StringIO(archive.read("observed/" + name).decode(), newline=""))

        manifest = json.loads(archive.read("observed/SOURCE_MANIFEST_09.json"))
        cases = []
        for kind, table in (("intervention", "EVENT_OUTCOMES.csv"), ("matched_control", "CONTROL_OUTCOMES.csv")):
            for row in rows(table):
                start = datetime.fromisoformat(row["start_naive"])
                ticks = []
                for tick in rows(row["trace"]):
                    for key in COLUMNS:
                        tick[key] = int(tick[key]) if tick[key] != "" else None
                    tick["relative_seconds"] = int((datetime.fromisoformat(tick["native_time"]) - start).total_seconds())
                    ticks.append(tick)
                cases.append({
                    "kind": kind,
                    "id": row["replay_id"],
                    "ahu": row["ahu"],
                    "start": row["start_naive"],
                    "end_exclusive": row["end_naive_exclusive"],
                    "observations": ticks,
                    "archived_outcome": {key: value for key, value in row.items() if key not in EVALUATION_FIELDS},
                    "evaluation_metadata": {key: value for key, value in row.items() if key in EVALUATION_FIELDS},
                })

        return (json.dumps({
            "provenance": {
                **{key: manifest[key] for key in ("dataset_doi", "version", "license", "dataset_url",
                                                  "article_doi", "rule_version", "site_count",
                                                  "intervention_event_day_count", "protocol_sha256")},
                "stage09_zip_sha256": STAGE09_SHA,
                "source_manifest_sha256": hashes["observed/SOURCE_MANIFEST_09.json"],
                "cadence_seconds": 300,
                "clock": "UNKNOWN_CLOCK_NAIVE_WORKBOOK_300S",
                "timestamp_column": "Time",
                "input_columns": COLUMNS,
                "files": {name: {key: record[key] for key in ("file_id", "bytes", "publisher_sha256", "verified_sha256")}
                          for name, record in manifest["files"].items()},
            },
            "cases": cases,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(freeze(args.archive))
    print(sha256(args.output.read_bytes()).hexdigest(), args.output.name)
