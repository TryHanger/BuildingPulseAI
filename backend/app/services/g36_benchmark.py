"""G36-5wk descriptive simulation benchmark with an explicit BASIC boundary."""
import csv
import hashlib
import io
from bisect import bisect_left
from functools import lru_cache

from backend.app.services import investigator_v1 as runtime
from backend.app.services.g36_policy import BASIC, HOLD, POLICY, STEP, THRESHOLD_K, WEATHER, evaluate, number

START = 16_354_800
END = 18_730_800
SOURCES = {
    "NOMINAL": ("BaselineSystem.csv", "fe744430e7800d6d33847137346032501e63f0cd30fec6bef9b41b0f8ec1569d"),
    "VALVE_CLOSED": ("CooCoiValStuck_0.csv", "b71d2aa060bd126376848c2826e4990f53986b3f665b2c670c75ad01ebef0ff9"),
    "DAMPER_OPEN": ("OADamStuck_100.csv", "18dd3dbc16adead32dc9233b408b42462994a353c4badc1c5efe409977f610b0"),
    "DUCT_LEAK": ("SupDucLea_20.csv", "793fc4819831b71bd065c549f9a8903a8ee86391b5f80ec207ba74ccf5ebce46"),
}
SCENARIO_LABELS = {
    "NOMINAL": "PUBLISHER_NOMINAL",
    "VALVE_CLOSED": "SIMULATED_VALVE_CLOSURE_INTERVAL",
    "DAMPER_OPEN": "SIMULATED_DAMPER_OPEN_INTERVAL",
    "DUCT_LEAK": "SIMULATED_DUCT_LEAK_INTERVAL",
}
ROLES = {
    "sat_k": ("MEASUREMENT", "K"), "setpoint_k": ("SETPOINT", "K"), "mat_k": ("MEASUREMENT", "K"),
    "fan_status": ("SIMULATED_STATUS", "binary"), "cooling_command": ("COMMAND", "fraction"),
    "heating_command": ("COMMAND", "fraction"),
}
ORACLE = "True Value for AHU Cooling Coil Valve Stuck Position (fraction, 0: fully closed to 1: fully open)"


def summarize(period, rows, *, step=STEP):
    counts = dict(period=period, samples=len(rows), applicable=0, point_exceedances=0, confirmed_samples=0, symptom_starts=0)
    reasons = {}
    previously_confirmed = False
    previous_time = None
    for sample, result in zip(rows, evaluate(rows, step=step)):
        reason = result["reason"]
        counts["applicable"] += reason == "APPLICABLE"
        counts["point_exceedances"] += result["point_exceeds"]
        confirmed = result["confirmed"]
        counts["confirmed_samples"] += confirmed
        counts["symptom_starts"] += confirmed and (not previously_confirmed or sample["time_s"] - previous_time != step)
        previously_confirmed = confirmed
        previous_time = sample["time_s"]
        if reason != "APPLICABLE":
            reasons[reason] = reasons.get(reason, 0) + 1
    return {**counts, "abstentions": reasons}


@lru_cache(maxsize=4)
def load_source(path, signature, expected_sha):
    try:
        payload = path.read_bytes()
        actual_signature = runtime.file_signature(path.stat())
    except FileNotFoundError:
        runtime.fail(404, "G36_SOURCE_UNAVAILABLE", "Install the verified G36-5wk source artifact")
    if actual_signature != signature or hashlib.sha256(payload).hexdigest() != expected_sha:
        runtime.fail(409, "G36_SOURCE_INTEGRITY", "G36-5wk source differs from the frozen digest")
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if not {"time (s)", ORACLE, *BASIC.values()} <= set(reader.fieldnames or []):
        runtime.fail(409, "G36_SOURCE_SCHEMA", "A required G36-5wk point is missing")
    samples, references = [], []
    for row in reader:
        value = number(row["time (s)"])
        if value is None or not value.is_integer() or (samples and value <= samples[-1]["time_s"]):
            runtime.fail(409, "G36_SOURCE_CLOCK", "Expected increasing integer model seconds")
        weather_known = all(number(row.get(column)) is not None for column in WEATHER)
        samples.append({"time_s": int(value), "weather_known": weather_known,
                        **{key: number(row[column]) for key, column in BASIC.items()}})
        references.append(number(row[ORACLE]))
    if not samples:
        runtime.fail(409, "G36_SOURCE_SCHEMA", "No observations in registered source")
    return samples, references, list(evaluate(samples))


def registered_source(scenario):
    filename, digest = SOURCES[scenario]
    path = runtime.settings.data_dir / "g36-5wk" / filename
    try:
        signature = runtime.file_signature(path.stat())
    except FileNotFoundError:
        runtime.fail(404, "G36_SOURCE_UNAVAILABLE", "Install the verified G36-5wk source artifact")
    return filename, digest, load_source(path, signature, digest)


def evidence_roots():
    return [{"point": key, "source_column": column, "role": ROLES[key][0], "unit": ROLES[key][1]}
            for key, column in BASIC.items()]


def benchmark(scenario, panel, start, limit):
    filename, digest, (rows, reference, evaluations) = registered_source(scenario)
    key = lambda row: row["time_s"]
    begin = bisect_left(rows, start, key=key)
    finish = min(begin + limit, len(rows))
    injection = bisect_left(rows, START, key=key)
    recovery = bisect_left(rows, END, key=key)
    positive = scenario != "NOMINAL"
    phases = ("PRE_INJECTION_NOMINAL", SCENARIO_LABELS[scenario], "UNKNOWN_POST_WINDOW") if positive else (
        "NOMINAL_PRE_WINDOW", "NOMINAL_COMPARISON_WINDOW", "NOMINAL_POST_WINDOW"
    )
    summaries = [summarize(phase, rows[lo:hi])
                 for phase, lo, hi in zip(phases, (0, injection, recovery), (injection, recovery, len(rows)))]
    return {
        "dataset_id": "g36-5wk", "provenance": "SIMULATED_BENCHMARK", "source_clock": "MODEL_SECONDS",
        "policy_id": POLICY, "sample_seconds": STEP, "threshold_k": THRESHOLD_K, "confirmation_seconds": HOLD,
        "scope": "EXPLORATORY_POST_HOC",
        "cause_status": "NOT_ASSESSED", "cooling_enable": "UNKNOWN",
        "evidence_roots": evidence_roots(),
        "scenario": scenario, "panel": panel, "source_file": filename, "source_sha256": digest,
        "first_time_s": rows[0]["time_s"], "last_time_s": rows[-1]["time_s"],
        "next_start": rows[finish]["time_s"] if finish < len(rows) else None,
        "summaries": summaries,
        "points": [{
            "time_s": rows[index]["time_s"], **{key: rows[index][key] for key in BASIC}, **evaluations[index],
            "gap_before": index > 0 and rows[index]["time_s"] - rows[index-1]["time_s"] != STEP,
            "label": (phases[0 if index < injection else 1 if index < recovery else 2] if positive else "PUBLISHER_NOMINAL"),
            "reference_oracle": reference[index] if panel == "EXTRA_SIMULATED" else None,
        } for index in range(begin, finish)],
    }


def command_distribution(commands):
    edges = ((0.20, 0.50), (0.50, 0.80), (0.80, 0.95), (0.95, 1.0))
    return {
        **{f"[{lo:.2f},{hi:.2f})": sum(lo <= value < hi for value in commands) for lo, hi in edges},
        "1.00": commands.count(1.0),
    }


def comparison():
    results = []
    for scenario in SOURCES:
        filename, digest, (rows, _, evaluated) = registered_source(scenario)
        active = [row for row in rows if START <= row["time_s"] < END]
        commands = [row["cooling_command"] for row, result in zip(rows, evaluated)
                    if START <= row["time_s"] < END and result["method_status"] == "APPLICABLE"]
        summary = summarize("ACTIVE_COMPARISON_WINDOW", active)
        results.append({
            "scenario": scenario, "label": SCENARIO_LABELS[scenario],
            "source_file": filename, "source_sha256": digest,
            "summary": summary, "episode_starts": summary["symptom_starts"],
            "cooling_command_bins": command_distribution(commands),
        })
    return {
        "dataset_id": "g36-5wk", "provenance": "SIMULATED_BENCHMARK", "scope": "EXPLORATORY_POST_HOC",
        "policy_id": POLICY, "start_s": START, "end_exclusive_s": END, "sample_seconds": STEP, "runs": results,
    }
