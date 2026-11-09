"""Independent vectorized calculation and source profile for the frozen G36 experiment."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

START, END, STEP = 16354800, 18730800, 300
SAT = "AHU Supply Air Temperature (°K)"
SP = "AHU Supply Air Temperature Setpoint (°K)"
MAT = "AHU Mixed Air Temperature (°K)"
OAT = "AHU Outdoor Air Dry Bulb Temperature (°K)"
OWB = "AHU Outdoor Air Wet Bulb Temperature (°K)"
FAN = "AHU Supply Air Fan Status (0: off, 1: on)"
COOL = "Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)"
HEAT = "Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)"
ORACLE = "True Value for AHU Cooling Coil Valve Stuck Position (fraction, 0: fully closed to 1: fully open)"
OCCUPIED = "Indicator if the System Operates in Occupied Mode (0: unoccupied mode, 1: occupied mode)"
TIME = "time (s)"


def independent(frame):
    valid = (frame[[SAT, SP, MAT]].ge(230) & frame[[SAT, SP, MAT]].le(340)).all(axis=1)
    valid &= frame[FAN].isin([0, 1]) & frame[COOL].between(0, 1) & frame[HEAT].between(0, 1)
    reasons = np.select(
        [~valid, frame[FAN].eq(0), frame[COOL].lt(.20), frame[HEAT].gt(.01), frame[MAT].sub(frame[SP]).lt(2)],
        ["INVALID_INPUT", "FAN_OFF", "LOW_COOLING_COMMAND", "HEATING_COMMAND", "LOW_TEMPERATURE_LIFT"],
        default="APPLICABLE",
    )
    applicable = pd.Series(reasons == "APPLICABLE", index=frame.index)
    score = frame[SAT].sub(frame[SP]).where(applicable)
    exceed = score.gt(2)
    continues = frame[TIME].diff().eq(STEP)
    starts = exceed & ~(exceed.shift(fill_value=False) & continues)
    first = frame[TIME].where(starts).ffill()
    confirmed = exceed & frame[TIME].sub(first).ge(600)
    return {
        "samples": len(frame), "applicable": int(applicable.sum()), "point_exceedances": int(exceed.sum()),
        "confirmed_samples": int(confirmed.sum()),
        "symptom_starts": int((confirmed & ~(confirmed.shift(fill_value=False) & continues)).sum()),
        "abstentions": {k: int(v) for k, v in pd.Series(reasons).value_counts().items() if k != "APPLICABLE"},
    }, (applicable, score, exceed, confirmed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--http-window", type=Path)
    args = parser.parse_args()
    frames = {p.stem: pd.read_csv(p, float_precision="round_trip") for p in sorted(args.source.glob("*.csv"))}
    nominal = frames["BaselineSystem"]
    inputs = {}
    pre = nominal[TIME].lt(START)
    active = nominal[TIME].ge(START) & nominal[TIME].lt(END)
    for name, frame in frames.items():
        assert frame.columns.equals(nominal.columns)
        assert frame[TIME].equals(nominal[TIME].astype(frame[TIME].dtype))
        inputs[name] = {
            "rows": len(frame), "columns": len(frame.columns), "duplicate_rows": int(frame.duplicated().sum()),
            "duplicate_ticks": int(frame[TIME].duplicated().sum()), "missing_cells": int(frame.isna().sum().sum()),
            "first": int(frame[TIME].iloc[0]), "last": int(frame[TIME].iloc[-1]),
            "step_histogram": {str(k): int(v) for k,v in frame[TIME].diff().dropna().value_counts().items()},
            "exact_pre_rows": int(frame.loc[pre].eq(nominal.loc[pre]).all(axis=1).sum()),
            "different_from_nominal": {key: int(frame[key].ne(nominal[key]).sum()) for key in (OAT, OWB, OCCUPIED, SP, FAN)},
            "active_valve_oracle_min_max": [float(frame.loc[active,ORACLE].min()), float(frame.loc[active,ORACLE].max())],
            "active_oracle_differs_from_command": int(frame.loc[active,ORACLE].ne(frame.loc[active,COOL]).sum()),
        }
    expected = json.loads(args.summary.read_text())
    for scenario, key in [("NOMINAL","BaselineSystem"), ("VALVE_CLOSED","CooCoiValStuck_0")]:
        frame = frames[key]
        for mask, saved in zip((pre, active, nominal[TIME].ge(END)), expected[scenario], strict=True):
            assert independent(frame[mask])[0] == {k: v for k,v in saved.items() if k != "period"}, (scenario, saved)
    if args.http_window:
        frame = frames["CooCoiValStuck_0"]
        applicable, score, exceed, confirmed = independent(frame)[1]
        row_for_time = {time: i for i, time in frame[TIME].items()}
        window = json.loads(args.http_window.read_text())
        for point in window["points"]:
            i = row_for_time[point["time_s"]]
            assert point["point_exceeds"] == bool(exceed[i]) and point["confirmed"] == bool(confirmed[i])
            assert point["residual_k"] == (float(score[i]) if applicable[i] else None)
            assert point["sat_k"] == float(frame.at[i,SAT]) and point["cooling_command"] == float(frame.at[i,COOL])
            assert point["reference_oracle"] == float(frame.at[i,ORACLE])
    result = {"source_profiles": inputs, "columns": nominal.columns.tolist(), "summary_parity": True,
              "http_window_parity": args.http_window is not None}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print("PASS independent vectorized period counts and registered source profile"
          + (" with HTTP evidence point parity" if args.http_window else ""))


if __name__ == "__main__":
    main()
