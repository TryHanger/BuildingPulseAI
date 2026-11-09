"""Standalone G5.4 CLI and projected scoring for one verified G36-1wk run."""
import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from math import fsum
from pathlib import Path

from backend.app.services.g36_policy import BASIC, HOLD, POLICY, THRESHOLD_K, WEATHER, evaluate, number

STEP = 60
FIRST = 17_625_600
LAST = 18_230_400
TICKS = 10_081
SOURCES = {
    "BaselineSystem.csv": "624e3c4e823e265e98d7c982f8498718b263ab1aff4d3fb4f2eb5ff787d370b3",
    "CooCoiValStuck_0.csv": "46c3e2833a5baddc7159d4424ad0d9e072d1cda06c10c1a96dfcba12c5f94a59",
}
SCOPE = "UNPAIRED_DESCRIPTIVE"
REVIEW = "NOT_BLIND_PREVIEWED_SOURCE"
IMPLEMENTATION = "g54-standalone-v1"


def verified_payload(path):
    if path.name not in SOURCES:
        raise ValueError("Unregistered G36-1wk source filename")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCES[path.name]:
        raise ValueError("G36-1wk source hash differs from the registered filename")
    return raw


def project_samples(raw):
    """Read only timestamp, six BASIC points and a weather validity flag."""
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    header = next(reader, [])
    required = ("time (s)", *BASIC.values(), *WEATHER)
    if not all(header.count(name) == 1 for name in required):
        raise ValueError("Missing, duplicated or wrong-unit BASIC/weather header")
    time_i, *indexes = (header.index(name) for name in required)
    basic_i, dry_i, wet_i = indexes[:-2], indexes[-2], indexes[-1]
    for fields in reader:
        if len(fields) != len(header):
            raise ValueError("CSV row width differs from registered header")
        time = number(fields[time_i])
        if time is None or not time.is_integer():
            raise ValueError("Expected integer model seconds")
        dry, wet = number(fields[dry_i]), number(fields[wet_i])
        yield {
            "time_s": int(time),
            "weather_known": dry is not None and wet is not None and 230 <= wet <= dry <= 340,
            **{key: number(fields[index]) for key, index in zip(BASIC, basic_i, strict=True)},
        }


def score(samples):
    samples = tuple(samples)
    previous_confirmed = False
    for sample, result in zip(samples, evaluate(samples, step=STEP), strict=True):
        confirmed = result["confirmed"]
        yield {"time_s": sample["time_s"], **result, "confirmed_start": confirmed and not previous_confirmed}
        previous_confirmed = confirmed


def distribution(values):
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        raise ValueError("No applicable G36-1wk observations")

    def quantile(p):
        rank = (count - 1) * p
        lower = int(rank)
        upper = min(lower + 1, count - 1)
        return ordered[lower] + (rank - lower) * (ordered[upper] - ordered[lower])

    return {
        "unit": "K", "count": count, "min": ordered[0], "p05": quantile(.05), "p25": quantile(.25),
        "median": quantile(.50), "p75": quantile(.75), "p95": quantile(.95), "max": ordered[-1],
        "mean": fsum(ordered) / count,
    }


def load_run(path):
    samples = list(project_samples(verified_payload(path)))
    times = [row["time_s"] for row in samples]
    if len(times) != TICKS or times != list(range(FIRST, LAST + STEP, STEP)):
        raise ValueError("G36-1wk source differs from the registered full minute grid")
    points = list(score(samples))
    residuals = distribution([point["residual_k"] for point in points if point["residual_k"] is not None])
    applicable = residuals["count"]
    summary = {
        "period": "FULL_RUN", "samples": len(points), "applicable": applicable,
        "point_exceedances": sum(point["point_exceeds"] for point in points),
        "confirmed_samples": sum(point["confirmed"] for point in points),
        "symptom_starts": sum(point["confirmed_start"] for point in points),
        "abstentions": dict(Counter(point["reason"] for point in points if point["method_status"] != "APPLICABLE")),
    }
    return samples, points, summary, residuals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args()
    _, points, summary, residuals = load_run(args.source)
    report = {
        "scope": SCOPE, "source_review": REVIEW, "source_type": "SIMULATION_ONLY",
        "implementation": IMPLEMENTATION, "policy_id": POLICY, "sample_seconds": STEP,
        "threshold_k": THRESHOLD_K, "confirmation_seconds": HOLD,
        "source_file": args.source.name, "source_sha256": SOURCES[args.source.name],
        "summary": summary, "coverage": summary["applicable"] / summary["samples"],
        "residual_distribution": residuals,
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if args.trace:
        with args.trace.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(points[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(points)


if __name__ == "__main__":
    main()
