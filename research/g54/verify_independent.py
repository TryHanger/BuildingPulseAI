"""Independent vectorized G5.4 reconciliation and optional actual HTTP seek checks."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd

TIME = "time (s)"
SAT = "AHU Supply Air Temperature (°K)"
SP = "AHU Supply Air Temperature Setpoint (°K)"
MAT = "AHU Mixed Air Temperature (°K)"
FAN = "AHU Supply Air Fan Status (0: off, 1: on)"
COOL = "Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)"
HEAT = "Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)"
DRY = "AHU Outdoor Air Dry Bulb Temperature (°K)"
WET = "AHU Outdoor Air Wet Bulb Temperature (°K)"
CASES = {"BaselineSystem": "NOMINAL", "CooCoiValStuck_0": "VALVE_CLOSED"}


def vectorized(frame):
    clock = frame[TIME]
    weather = frame[WET].ge(230) & frame[WET].le(frame[DRY]) & frame[DRY].le(340)
    valid = (frame[[SAT, SP, MAT]].ge(230) & frame[[SAT, SP, MAT]].le(340)).all(axis=1)
    valid &= frame[FAN].isin([0, 1]) & frame[COOL].between(0, 1) & frame[HEAT].between(0, 1)
    reasons = np.select(
        [~weather, ~valid, frame[FAN].eq(0), frame[COOL].lt(.20), frame[HEAT].gt(.01), frame[MAT].sub(frame[SP]).lt(2)],
        ["UNKNOWN_WEATHER_CONTEXT", "INVALID_INPUT", "FAN_OFF", "LOW_COOLING_COMMAND", "HEATING_COMMAND", "LOW_TEMPERATURE_LIFT"],
        default="APPLICABLE",
    )
    applicable = pd.Series(reasons == "APPLICABLE")
    residual = frame[SAT].sub(frame[SP]).where(applicable)
    exceed = residual.gt(2)
    continuous = clock.diff().eq(60)
    segment = (~(exceed & exceed.shift(fill_value=False) & continuous)).cumsum()
    start = clock.groupby(segment).transform("min")
    confirmed = exceed & clock.sub(start).ge(600)
    starts = confirmed & ~(confirmed.shift(fill_value=False) & continuous)
    unknown = np.isin(reasons, ["INVALID_INPUT", "UNKNOWN_WEATHER_CONTEXT"])
    return pd.DataFrame({
        "time_s": clock.astype(int), "reason": reasons, "residual_k": residual, "point_exceeds": exceed,
        "confirmed": confirmed, "confirmed_start": starts,
        "weather_status": np.where(weather, "OBSERVED", "UNKNOWN"),
        "fan_mode": np.select([frame[FAN].eq(1), frame[FAN].eq(0)], ["FAN_ON", "FAN_OFF"], default="UNKNOWN"),
        "method_status": np.where(applicable, "APPLICABLE", np.where(unknown, "INCONCLUSIVE", "INAPPLICABLE")),
        "predicate": np.where(applicable, np.where(exceed, "VIOLATED", "NOT_VIOLATED"), "INDETERMINATE"),
    })


def get(base, **query):
    url = f"{base}/api/v1/g36-benchmark?{urlencode(query)}"
    with urlopen(url, timeout=20) as response:
        return json.load(response)


def check_seek(base, scenario, independent, report):
    query = {"dataset": "g36-1wk", "scenario": scenario, "panel": "BASIC"}
    first_confirmations = independent.index[independent["confirmed_start"]].tolist()
    indices = sorted({0, 1, len(independent)//2, len(independent)-2, len(independent)-1,
                      *(max(0, i-1) for i in first_confirmations), *first_confirmations,
                      *(min(len(independent)-1, i+1) for i in first_confirmations)})
    observed = {}
    for i in indices:
        time = int(independent.at[i, "time_s"])
        response = get(base, **query, start=time, limit=3)
        assert response["summaries"] == [report["summary"]]
        assert response["scope"] == "UNPAIRED_DESCRIPTIVE"
        assert response["cause_status"] == "NOT_ASSESSED" and response["cooling_enable"] == "UNKNOWN"
        for returned, (_, expected) in zip(response["points"], independent.iloc[i:i+3].iterrows(), strict=True):
            for key in independent.columns:
                value = expected[key]
                assert returned[key] == (None if pd.isna(value) else value), (scenario, time, key)
            assert returned["reference_oracle"] is None
        observed[str(time)] = [row["time_s"] for row in response["points"]]
    tail = get(base, dataset="g36-1wk", scenario=scenario, panel="EXTRA_SIMULATED", start=18230340, limit=2)
    basic_tail = get(base, **query, start=18230340, limit=2)
    assert [{**point, "reference_oracle": None} for point in tail["points"]] == basic_tail["points"]
    assert [row["time_s"] for row in tail["points"]] == [18230340,18230400]
    if scenario == "VALVE_CLOSED":
        assert [row["reference_oracle"] for row in tail["points"]] == [1, 1]
    return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("outputs", type=Path)
    parser.add_argument("--url")
    args = parser.parse_args()
    receipts = {}
    for name, scenario in CASES.items():
        path = args.source/f"{name}.csv"
        report = json.loads((args.outputs/f"{name}-summary.json").read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == report["source_sha256"]
        frame = pd.read_csv(path, usecols=[TIME, SAT, SP, MAT, FAN, COOL, HEAT, DRY, WET], float_precision="round_trip")
        independent = vectorized(frame)
        trace = pd.read_csv(args.outputs/f"{name}-trace.csv", float_precision="round_trip")
        pd.testing.assert_frame_equal(independent[trace.columns], trace, check_exact=True)
        residuals = independent["residual_k"].dropna().to_numpy()
        summary = {
            "period": "FULL_RUN", "samples": len(independent), "applicable": len(residuals),
            "point_exceedances": int(independent["point_exceeds"].sum()), "confirmed_samples": int(independent["confirmed"].sum()),
            "symptom_starts": int(independent["confirmed_start"].sum()),
            "abstentions": dict(Counter(independent.loc[independent["reason"] != "APPLICABLE","reason"])),
        }
        assert summary == report["summary"] and report["coverage"] == len(residuals)/len(independent)
        stats = dict(zip(("min","p05","p25","median","p75","p95","max"),
                         np.quantile(residuals, [0,.05,.25,.50,.75,.95,1]), strict=True))
        stats["mean"] = np.mean(residuals)
        for key,value in stats.items():
            assert abs(value-report["residual_distribution"][key]) <= 1e-12
        receipt = {"matched_points": len(independent), "confirmed_start_times": independent.loc[independent["confirmed_start"],"time_s"].tolist()}
        if args.url:
            receipt["http_direct_seek"] = check_seek(args.url, scenario, independent, report)
        receipts[name] = receipt
        print(f"PASS {name}: {len(independent)} matched points, summary, quantiles and confirmed starts")
    (args.outputs/"independent-parity.json").write_text(json.dumps(receipts,indent=2)+"\n")


if __name__ == "__main__":
    main()
