"""Metadata and coverage audit only. No model or residual computation."""
import argparse
import json
from pathlib import Path

import numpy as np

from research.ml_transfer_05.contract import ContractError, block_rows, blocks, load_protocol, masks, read_input


def profile(data, protocol):
    denominator, eligible = masks(data, protocol)
    labels = blocks(data, protocol)
    rows = [row for _, _, row in block_rows(labels, denominator, eligible, protocol)]
    complete = labels.astype(str).isin({row["block"] for row in rows})
    counts = {
        "rows": len(labels), "incomplete_boundary_rows": int((~complete).sum()),
        "raw_header_sha256": data.header_sha256,
        "missing_by_channel": {key: int(value) for key, value in data.channels.isna().sum().items()},
        "warm_running_minutes": int((denominator & complete).sum()),
        "usable_minutes_before_train_support": int((eligible & complete).sum()),
        "evaluable_blocks_before_train_support": sum(row["status"] == "EVALUABLE" for row in rows),
    }
    if data.role != "source":
        mode = protocol["audit_only"]["target_cooling_mode"]["header"]
        counts["warm_running_minutes_by_plant_mode"] = {
            str(code): int(count) for code, count in data.context.loc[denominator & complete, mode].value_counts().items()
        }
        counts["model_time_blocks"] = rows
    return counts


def target_context_difference(reference, probe, protocol):
    if not reference.clock.equals(probe.clock):
        raise ContractError("TARGET_GRID_MISMATCH")
    fields = {
        "OA_TEMP_degF": (reference.channels.OA_TEMP, probe.channels.OA_TEMP),
        "SAT_SETPOINT_degF": (reference.channels.SA_TEMPSPT, probe.channels.SA_TEMPSPT),
        "SF_STATUS": (reference.channels.SF_STATUS, probe.channels.SF_STATUS),
        **{name: (reference.context[name], probe.context[name]) for name in reference.context},
    }
    return {name: {"different_ticks": int((~np.isclose(left, right, atol=1e-9, rtol=0, equal_nan=True)).sum()),
                   "max_abs_difference": float(np.nanmax(np.abs(left - right)))}
            for name, (left, right) in fields.items()}


def main(inputs, output):
    protocol = load_protocol()
    data = {role: read_input(inputs, role) for role in protocol["files"]}
    result = {"status": "STOP_BEFORE_TARGET_SCORE", "target_prediction_executed": False,
              "source_target_rows_joined_for_training": False,
              "inputs": {role: profile(values, protocol) for role, values in data.items()},
              "target_context_differences": target_context_difference(data["target_reference"], data["target_probe"], protocol),
              "paired_causal_design": False}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("PASS pinned bytes, schemas, clocks and model-free coverage; STOP_BEFORE_TARGET_SCORE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
