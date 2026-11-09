"""Build a reproducible sparse index from the frozen raw sources outside the request path."""
import argparse
import hashlib
import json
import resource
from collections import Counter
from pathlib import Path
from time import perf_counter, process_time

import pandas as pd

from backend.app.services import investigator_v1 as runtime
from backend.app.services.g2_mode import HOLD_SECONDS
from backend.app.services.g3_incidents import window_evaluations
from backend.app.services.g3_symptom import EpisodeAccumulator, ROLES, RULE_FINGERPRINT, verified_bindings


def analyze_source(source):
    path = runtime.source_path(source)
    signature = runtime.file_signature(path.stat())
    runtime.verify_file(path, source["sha256"], signature)
    accumulator = EpisodeAccumulator()
    prior = None
    counts = Counter()
    with pd.read_csv(path, usecols=lambda name: name == "Datetime" or name in ROLES,
                     chunksize=4096, float_precision="round_trip") as chunks:
        for chunk in chunks:
            frame = runtime.source_frame(chunk)
            prefix = len(prior) if prior is not None else 0
            if prefix:
                if prior.index[-1] >= frame.index[0]:
                    raise ValueError("Raw source time is not increasing across chunks")
                frame = pd.concat([prior, frame])
            for stamp, result in window_evaluations(frame, prefix, len(frame), runtime.SIGNALS):
                counts[result.predicate] += 1
                accumulator.feed(stamp, result)
            prior = frame.tail(HOLD_SECONDS // runtime.SAMPLE_SECONDS)
    if runtime.file_signature(path.stat()) != signature or sum(counts.values()) != source["rows"]:
        raise ValueError("The raw source changed or coverage differs from the manifest")
    return {"source_sha256": source["sha256"], "coverage": dict(sorted(counts.items())),
            "episodes": accumulator.finish()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not verified_bindings(runtime.SIGNALS):
        raise ValueError("Required BASIC bindings are unverified")
    datasets = {}
    for key, source in sorted(runtime.SOURCES.items()):
        wall, cpu = perf_counter(), process_time()
        record = analyze_source(source)
        datasets[key] = record
        print(json.dumps({"dataset_id": key, "rows": source["rows"], "coverage": record["coverage"],
                          "episodes": len(record["episodes"]), "wall_seconds": round(perf_counter() - wall, 3),
                          "cpu_seconds": round(process_time() - cpu, 3),
                          "rss_peak_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}), flush=True)
    encoded = (json.dumps({"index_version": 1, "rule_fingerprint": RULE_FINGERPRINT, "datasets": datasets},
                          sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    args.output.write_bytes(encoded)
    args.output.with_suffix(".sha256").write_text(hashlib.sha256(encoded).hexdigest() + "\n")


if __name__ == "__main__":
    main()
