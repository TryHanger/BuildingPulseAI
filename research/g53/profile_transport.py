"""Pre-score identity, schema and weather checks for the Figshare CoolingSeason pair."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

HASHES = {
    "BaselineSystem.csv": "624e3c4e823e265e98d7c982f8498718b263ab1aff4d3fb4f2eb5ff787d370b3",
    "CooCoiValStuck_0.csv": "46c3e2833a5baddc7159d4424ad0d9e072d1cda06c10c1a96dfcba12c5f94a59",
}
TIME = "time (s)"
WEATHER = ["AHU Outdoor Air Dry Bulb Temperature (°K)", "AHU Outdoor Air Wet Bulb Temperature (°K)"]
FAN = "AHU Supply Air Fan Status (0: off, 1: on)"
SETPOINT = "AHU Supply Air Temperature Setpoint (°K)"
OCCUPIED = "Indicator if the System Operates in Occupied Mode (0: unoccupied mode, 1: occupied mode)"
ORACLE = "True Value for AHU Cooling Coil Valve Stuck Position (fraction, 0: fully closed to 1: fully open)"
BASIC = [
    "AHU Supply Air Temperature (°K)", SETPOINT, "AHU Mixed Air Temperature (°K)", FAN,
    "Control Signal for AHU Cooling Coil Valve from BAS (fraction, 0: valve should be fully closed to 1: valve should be fully open)",
    "Control Signal for AHU Heating Coil Valve (fraction, 0: valve should be fully closed to 1: valve should be fully open)",
]


def profile(root):
    frames, receipts = [], {}
    for name, digest in HASHES.items():
        path = root / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
        frame = pd.read_csv(path, float_precision="round_trip")
        assert {TIME, ORACLE, OCCUPIED, *WEATHER, *BASIC} <= set(frame), name
        time = frame[TIME]
        assert len(frame) == 10081 and len(frame.columns) == 114
        assert not time.duplicated().any() and time.diff().dropna().eq(60).all()
        assert not frame[[*BASIC, *WEATHER, ORACLE]].isna().any().any(), name
        receipts[name] = {
            "sha256": digest, "bytes": path.stat().st_size, "rows": len(frame),
            "columns": len(frame.columns), "model_start_s": int(time.iloc[0]), "model_last_s": int(time.iloc[-1]),
            "step_s": 60, "missing_cells": int(frame.isna().sum().sum()),
            "duplicate_rows": int(frame.duplicated().sum()), "fan_values": sorted(map(float, frame[FAN].unique())),
        }
        frames.append(frame)
    nominal, fault = frames
    assert nominal.columns.equals(fault.columns)
    assert nominal[TIME].eq(fault[TIME]).all()
    weather = {
        key: {
            "mismatched_ticks": int(nominal[key].ne(fault[key]).sum()),
            "max_absolute_delta_k": float(nominal[key].sub(fault[key]).abs().max()),
        } for key in WEATHER
    }
    oracle_exceptions = [
        {"time_s": int(t), "reference_oracle": float(value)}
        for t, value in fault.loc[fault[ORACLE].ne(0), [TIME, ORACLE]].itertuples(index=False, name=None)
    ]
    matching_weather = not any(row["mismatched_ticks"] for row in weather.values())
    return {
        "files": receipts, "matching_model_clock": True, "matching_weather_dry_wet": matching_weather,
        "weather_comparison": weather, "fault_oracle_exceptions": oracle_exceptions,
        "transfer_gate": "IDENTITY_AND_CONTEXT_PASS" if matching_weather and not oracle_exceptions else "BLOCKED_BY_DATA",
        "score_computed": False,
        "same_named_columns": True, "columns": nominal.columns.tolist(), "basic_columns": BASIC,
        "weather_columns": WEATHER, "fault_oracle_always_zero": not oracle_exceptions,
        "mismatches": {key: int(nominal[key].ne(fault[key]).sum()) for key in (OCCUPIED, FAN, SETPOINT)},
        "pre_injection_rows_available": 0, "clock_kind": "MODEL_SECONDS",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = profile(args.source)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{result['transfer_gate']}: publisher SHA, BASIC schema and 60 s clock verified. No scoring.")
