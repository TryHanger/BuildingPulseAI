"""Rebuild the explicit synthetic source and its offline incident index."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from backend.app.services import investigator_v1 as runtime
from backend.app.services.g3_incidents import window_evaluations
from backend.app.services.g3_symptom import EpisodeAccumulator, ROLES, RULE_FINGERPRINT

def build(directory, *, omit_mat=False, violation_minutes=15):
    directory.mkdir(parents=True, exist_ok=True)
    first = datetime(2018, 1, 2, 11)
    path = directory / "mixing-demo.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        columns = [key for key in ROLES if key != "MA_TEMP" or not omit_mat]
        writer.writerow(["Datetime", *columns])
        for minute in [*range(22), *range(32, 42)]:
            stamp = first + timedelta(minutes=minute)
            values = dict(zip(ROLES, [18 if 5 <= minute < 5 + violation_minutes else 55, 40, 70, 1, 0.6]))
            writer.writerow([stamp.isoformat(), *(values[key] for key in columns)])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = runtime.read_verified(path, digest, runtime.file_signature(path.stat()))
    accumulator = EpisodeAccumulator()
    coverage = Counter()
    for stamp, evaluation in window_evaluations(frame, 0, len(frame), runtime.SIGNALS):
        coverage[evaluation.predicate] += 1
        accumulator.feed(stamp, evaluation)
    index = {"index_version": 1, "rule_fingerprint": RULE_FINGERPRINT,
             "datasets": {runtime.DEMO_ID: {"source_sha256": digest, "coverage": dict(coverage), "episodes": accumulator.finish()}}}
    encoded = (json.dumps(index, sort_keys=True, indent=2) + "\n").encode()
    (directory / "incidents.json").write_bytes(encoded)
    manifest = {"dataset_id": runtime.DEMO_ID, "name": "Синтетический эпизод MAT",
                "sha256": digest, "index_sha256": hashlib.sha256(encoded).hexdigest(),
                "rows": len(frame), "first": frame.index[0].isoformat(), "last": frame.index[-1].isoformat()}
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--omit-mat", action="store_true", help="Build a separate negative test fixture")
    args = parser.parse_args()
    build(args.output, omit_mat=args.omit_mat)
