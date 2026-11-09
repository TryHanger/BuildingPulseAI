"""Read-only window adapter for the registered G5.4 runs."""
import csv
import io
from functools import lru_cache

from backend.app.services import g36_benchmark, g36_week as week, investigator_v1 as runtime
from backend.app.services.g36_policy import BASIC, HOLD, POLICY, THRESHOLD_K, number

ORACLE_EXCEPTIONS = {
    ("VALVE_CLOSED", "46c3e2833a5baddc7159d4424ad0d9e072d1cda06c10c1a96dfcba12c5f94a59"):
        frozenset({18_230_340, 18_230_400}),
}

FILENAMES = {"NOMINAL": "BaselineSystem.csv", "VALVE_CLOSED": "CooCoiValStuck_0.csv"}


@lru_cache(maxsize=2)
def load_verified(path, signature):
    try:
        run = week.load_run(path)
        if runtime.file_signature(path.stat()) != signature:
            raise ValueError("G36-1wk source changed while reading")
        return run
    except FileNotFoundError:
        runtime.fail(404, "G36_SOURCE_UNAVAILABLE", "Install the verified G36-1wk source artifact")
    except ValueError as error:
        runtime.fail(409, "G36_SOURCE_INTEGRITY", str(error))


@lru_cache(maxsize=2)
def read_oracle(path, signature):
    try:
        raw = week.verified_payload(path)
        if runtime.file_signature(path.stat()) != signature:
            raise ValueError("G36-1wk source changed while reading")
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        index = next(reader).index(g36_benchmark.ORACLE)
        return [number(row[index]) for row in reader]
    except FileNotFoundError:
        runtime.fail(404, "G36_SOURCE_UNAVAILABLE", "Install the verified G36-1wk source artifact")
    except ValueError as error:
        runtime.fail(409, "G36_SOURCE_INTEGRITY", str(error))


def benchmark(scenario, panel, start, limit):
    if scenario not in FILENAMES:
        runtime.fail(422, "UNKNOWN_G36_1WK_SCENARIO", "Use NOMINAL or VALVE_CLOSED for 1wk")
    filename = FILENAMES[scenario]
    path = runtime.settings.data_dir / "g36-1wk" / filename
    try:
        signature = runtime.file_signature(path.stat())
    except FileNotFoundError:
        runtime.fail(404, "G36_SOURCE_UNAVAILABLE", "Install the verified G36-1wk source artifact")
    samples, points, summary, residuals = load_verified(path, signature)
    reference = read_oracle(path, signature) if panel == "EXTRA_SIMULATED" else None
    source_hash = week.SOURCES[filename]
    oracle_exceptions = ORACLE_EXCEPTIONS.get((scenario, source_hash), ())
    begin = min(week.TICKS, max(0, (start - week.FIRST + week.STEP - 1) // week.STEP))
    finish = min(begin + limit, week.TICKS)
    label = "PUBLISHER_NOMINAL" if scenario == "NOMINAL" else "PUBLISHER_VALVE_CLOSED_SCENARIO"
    return {
        "dataset_id": "g36-1wk", "provenance": "SIMULATED_BENCHMARK", "source_clock": "MODEL_SECONDS",
        "policy_id": POLICY, "sample_seconds": week.STEP, "threshold_k": THRESHOLD_K, "confirmation_seconds": HOLD,
        "scope": week.SCOPE, "source_review": week.REVIEW, "cause_status": "NOT_ASSESSED", "cooling_enable": "UNKNOWN",
        "evidence_roots": g36_benchmark.evidence_roots(),
        "paired_causal_gate": "STOP", "unpaired_descriptive_gate": "PASS", "runs_per_scenario": 1,
        "scenario": scenario, "panel": panel, "source_file": filename, "source_sha256": source_hash,
        "first_time_s": week.FIRST, "last_time_s": week.LAST,
        "next_start": points[finish]["time_s"] if finish < week.TICKS else None,
        "summaries": [summary], "residual_distribution": residuals,
        "points": [{
            **{key: samples[index][key] for key in BASIC}, **points[index],
            "label": label, "gap_before": False,
            "reference_oracle": reference[index] if reference is not None else None,
            **({"source_oracle_status": "SOURCE_ORACLE_EXCEPTION"}
               if reference is not None and points[index]["time_s"] in oracle_exceptions else {}),
        } for index in range(begin, finish)],
    }
