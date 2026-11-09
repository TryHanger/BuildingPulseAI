"""G5.7 descriptive, offline G36 section observations. No new diagnostic score."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
from statistics import median

from backend.app.services.g36_policy import BASIC, POLICY, WEATHER, evaluate, number

TIME = "time (s)"
COIL = "Cooling Coil Discharge Air Temperature (°K)"
SAT = BASIC["sat_k"]
GRID = {"5wk": (15_724_800, 18_748_800, 300), "1wk": (17_625_600, 18_230_400, 60)}
WINDOW = (16_354_800, 18_730_800)
EPSILON = 1e-9  # Numerical comparison of differences only, in K.
RUNS = (
    ("A", "5wk", "BaselineSystem.csv", "fe744430e7800d6d33847137346032501e63f0cd30fec6bef9b41b0f8ec1569d"),
    ("B", "5wk", "CooCoiValStuck_0.csv", "b71d2aa060bd126376848c2826e4990f53986b3f665b2c670c75ad01ebef0ff9"),
    ("C", "5wk", "OADamStuck_100.csv", "18dd3dbc16adead32dc9233b408b42462994a353c4badc1c5efe409977f610b0"),
    ("D", "5wk", "SupDucLea_20.csv", "793fc4819831b71bd065c549f9a8903a8ee86391b5f80ec207ba74ccf5ebce46"),
    ("E", "1wk", "BaselineSystem.csv", "624e3c4e823e265e98d7c982f8498718b263ab1aff4d3fb4f2eb5ff787d370b3"),
    ("F", "1wk", "CooCoiValStuck_0.csv", "46c3e2833a5baddc7159d4424ad0d9e072d1cda06c10c1a96dfcba12c5f94a59"),
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(raw, expected):
    if digest(raw) != expected:
        raise ValueError("Source hash mismatch, including possible temporal misalignment")


def column_positions(header):
    required = (TIME, *BASIC.values(), *WEATHER, COIL)
    if any(header.count(column) != 1 for column in required):
        raise ValueError("Missing, duplicate or wrong-unit header")
    if len(header) != 114 or header[46] != SAT or header[52] != COIL:
        raise ValueError("Unexpected SAT or coil-discharge column order")
    return {name: header.index(name) for name in required}


def project(raw, profile, grid):
    """Yield two projections from a single authenticated, synchronized export."""
    first, last, step = grid
    expected_times = range(first, last + step, step)
    stream = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    header = next(stream, [])
    positions = column_positions(header)
    basic, coils = [], []
    for expected, row in zip(expected_times, stream, strict=True):
        if len(row) != len(header):
            raise ValueError("Unexpected CSV row width")
        if number(row[positions[TIME]]) != expected:
            raise ValueError("Shift, gap or out-of-order model time")
        dry, wet = (number(row[positions[name]]) for name in WEATHER)
        weather_known = dry is not None and wet is not None
        if profile == "1wk":
            weather_known = weather_known and 230 <= wet <= dry <= 340
        basic.append({
            "time_s": expected, "weather_known": weather_known,
            **{key: number(row[positions[name]]) for key, name in BASIC.items()},
        })
        coils.append(number(row[positions[COIL]]))
    return basic, coils


def require_non_alias(samples, coils):
    pairs = [(sample["sat_k"], coil) for sample, coil in zip(samples, coils, strict=True)
             if valid_temperature(sample["sat_k"]) and valid_temperature(coil)]
    if not pairs:
        raise ValueError("STOP_NO_INCREMENTAL_VALUE: no valid coil and SAT pairs")
    if all(abs(sat - coil) <= EPSILON for sat, coil in pairs):
        raise ValueError("STOP_NO_INCREMENTAL_VALUE: coil discharge aliases SAT")


def valid_temperature(value):
    return value is not None and 230 <= value <= 340


def trace(samples, coils, step, period_eval, *, topology):
    require_non_alias(samples, coils)
    evaluations = evaluate(samples, step=step)
    for sample, coil, result, within_period in zip(samples, coils, evaluations, period_eval, strict=True):
        sat, mat, sp = (sample[key] for key in ("sat_k", "mat_k", "setpoint_k"))
        sat_valid, coil_valid = valid_temperature(sat), valid_temperature(coil)
        valid_pair = sat_valid and coil_valid
        common = result["method_status"] == "APPLICABLE" and valid_pair
        delta = sat - coil if valid_pair else None
        position = "AMBIGUOUS"
        direction = "AMBIGUOUS"
        if common and within_period["confirmed"]:
            position = "ABOVE_SP_AT_BOTH" if coil > sp else "CROSSES_SP_DOWNSTREAM"
            direction = "WARMS" if delta > EPSILON else "COOLS" if delta < -EPSILON else "NO_RESOLVED_CHANGE"
        yield {
            "time_s": sample["time_s"], "sat_present": sat is not None, "coil_present": coil is not None,
            "sat_valid_k": sat_valid, "coil_valid_k": coil_valid, "valid_pair": valid_pair,
            "common_mask": common, "fan_mode": result["fan_mode"], "cooling_enable": "UNKNOWN",
            "basic_reason": result["reason"], "basic_point_exceeds": result["point_exceeds"],
            "basic_confirmed_timeline": result["confirmed"], "basic_confirmed_period": within_period["confirmed"],
            "sat_minus_sp_k": result["residual_k"], "sat_k": sat, "coil_out_k": coil, "mat_k": mat,
            "sat_minus_coil_k": delta,
            "coil_minus_sat_sp_k": coil - sp if coil_valid and valid_temperature(sp) else None,
            "mat_minus_coil_k": mat - coil if topology and valid_temperature(mat) and coil_valid else None,
            "position_vs_sat_sp": position, "downstream_change": direction, "cause": "AMBIGUOUS",
        }


def groups(profile, samples):
    if profile == "1wk":
        return {"FULL": samples}
    start, end = WINDOW
    return {
        "PRE": [row for row in samples if row["time_s"] < start],
        "WINDOW": [row for row in samples if start <= row["time_s"] < end],
        "POST": [row for row in samples if row["time_s"] >= end],
    }


def stats(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    def quantile(p):
        rank = (len(values) - 1) * p
        lower = int(rank)
        return values[lower] + (rank - lower) * (values[min(lower + 1, len(values) - 1)] - values[lower])
    return {"n": len(values), "min": values[0], "p05": quantile(.05), "median": median(values),
            "p95": quantile(.95), "max": values[-1]}


def unavailable(rows, flag, step):
    blocks = []
    for row in rows:
        if row[flag]:
            continue
        time = row["time_s"]
        if blocks and time - blocks[-1]["last_s"] == step:
            blocks[-1]["last_s"] = time
            blocks[-1]["ticks"] += 1
        else:
            blocks.append({"first_s": time, "last_s": time, "ticks": 1})
    ticks = sum(block["ticks"] for block in blocks)
    return {"ticks": ticks, "duration_tick_seconds": ticks * step, "blocks": blocks}


def summarize(rows, step):
    common = [row for row in rows if row["common_mask"]]
    symptom = [row for row in common if row["basic_confirmed_period"]]
    positions = Counter(row["position_vs_sat_sp"] for row in symptom)
    directions = Counter(row["downstream_change"] for row in symptom)
    return {
        "total_ticks": len(rows), "first_s": rows[0]["time_s"], "last_s": rows[-1]["time_s"],
        "clock_gap_ticks": sum((right["time_s"] - left["time_s"]) // step - 1
                               for left, right in zip(rows, rows[1:])),
        "valid_pairs": sum(row["valid_pair"] for row in rows), "common_ticks": len(common),
        "basic_applicable": sum(row["basic_reason"] == "APPLICABLE" for row in rows),
        "basic_exceeds": sum(row["basic_point_exceeds"] for row in rows),
        "basic_confirmed_period": sum(row["basic_confirmed_period"] for row in rows),
        "basic_confirmed_timeline": sum(row["basic_confirmed_timeline"] for row in rows),
        "common_confirmed": len(symptom), "positions_confirmed": dict(positions),
        "directions_confirmed": dict(directions),
        "incremental_witness": len(positions) > 1 or {"WARMS", "COOLS"} <= directions.keys(),
        "unavailable": {key: unavailable(rows, key, step)
                        for key in ("sat_present", "coil_present", "sat_valid_k", "coil_valid_k")},
        "sat_minus_coil_k_by_fan": {
            fan: stats(row["sat_minus_coil_k"] for row in rows if row["valid_pair"] and row["fan_mode"] == fan)
            for fan in ("FAN_ON", "FAN_OFF", "UNKNOWN")
        },
        "sat_minus_coil_k_common": stats(row["sat_minus_coil_k"] for row in common),
        "sat_minus_coil_k_confirmed": stats(row["sat_minus_coil_k"] for row in symptom),
        "mat_minus_coil_k_confirmed": stats(row["mat_minus_coil_k"] for row in symptom
                                           if row["mat_minus_coil_k"] is not None),
        "cooling_enable": "UNKNOWN",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = {}
    for run, profile, name, expected in RUNS:
        raw = (args.data_root / f"g36-{profile}" / name).read_bytes()
        verify(raw, expected)
        samples, coils = project(raw, profile, GRID[profile])
        step = GRID[profile][2]
        periods = groups(profile, samples)
        evaluations = [item for period in periods.values() for item in evaluate(period, step=step)]
        rows = list(trace(samples, coils, step, evaluations, topology=True))
        by_period = {}
        offset = 0
        for period, subset in periods.items():
            end = offset + len(subset)
            by_period[period] = summarize(rows[offset:end], step)
            for row in rows[offset:end]:
                row["period"] = period
            offset = end
        with (args.output / f"trace-{run}.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        result[run] = {
            "profile": profile, "sha256": expected, "total_ticks": len(rows), "policy": POLICY,
            "periods": by_period,
        }
        print(f"PASS {run} {profile} {len(rows)} ticks", flush=True)
    decision = any(period["incremental_witness"] for run in result.values() for period in run["periods"].values())
    (args.output / "g57-observations.json").write_text(json.dumps({
        "decision": "SECTION_CONTEXT_SIM_ONLY" if decision else "STOP_NO_INCREMENTAL_VALUE",
        "runs": result,
    }, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
