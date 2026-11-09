"""Finish the interrupted output receipt from the already-written trace, without prediction."""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform

import pandas as pd

from research.ml_transfer_06 import target_normal_06 as normal


def main(directory, artifacts):
    started = json.loads((directory / "RUN_STARTED.json").read_text())
    if started["role"] != normal.ROLE or started["sha256"] != normal.PINNED or not started["target_normal_only"]:
        raise normal.ContractError("UNRECOGNIZED_NORMAL_EXECUTION")
    protocol = json.loads(normal.checked(normal.PROTOCOL, normal.PROTOCOL.name))
    fit = json.loads(normal.checked(artifacts / normal.FIT, normal.FIT))
    normal.checked_receipt(protocol, fit)
    trace_path = directory / "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"
    blocks_path = directory / "TARGET_NORMAL_06_BLOCKS.csv"
    trace = pd.read_csv(trace_path, float_precision="round_trip")
    blocks = pd.read_csv(blocks_path, float_precision="round_trip")
    mask = protocol["mask"]
    if len(trace) != mask["target_complete_blocks"] * mask["minutes_per_block"] or len(blocks) != mask["target_complete_blocks"]:
        raise normal.ContractError("INCOMPLETE_EXISTING_TRACE")
    tech = bool(trace[["FAN_STATUS", "OA_TEMP_degF", "PLANT_MODE"]].isna().any(axis=None)
                or trace.INVALID_UNIT_OR_RANGE.any())
    summary = normal.window_summary(trace, blocks.to_dict("records"), tech, protocol)
    versions = {"python": platform.python_version(), **{name: version(name) for name in ("lightgbm", "pandas", "numpy")}}
    normal.write_json(directory / "TARGET_NORMAL_06_RECEIPT.json", {
        "role": normal.ROLE, "source": normal.NORMAL, "sha256": normal.PINNED, "versions": versions,
        "ridge_runtime": "FROZEN_JSON_COEFFICIENTS_NUMPY", "features": list(normal.FEATURES),
        "alarm_operator": ">", "alarm_z": 3, "calibration": fit["calibration"],
        "source_support_degF": fit["train_support_degF"], "clock_basis": "MODEL_SECONDS",
        "excluded_right_boundary_model_s": 18230400, "independent_normal_runs": 1,
        "target_fault_prediction_executed": False, "target_normal_native_predict_calls": int(trace.ELIGIBLE.any()),
        "fault_phase_authorized": False, "artifacts": {path.name: normal.sha(path) for path in (trace_path, blocks_path)},
        "receipt_origin": "SEALED_EXISTING_SINGLE_RUN_TRACE_AFTER_POSTWRITE_AUDIT_DENIAL",
        "prediction_calls_during_receipt_recovery": 0,
        **summary,
    })
    print(summary["gate"] + " | sealed existing trace; no model loaded")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("directory", "artifacts"):
        parser.add_argument(arg, type=Path)
    main(**vars(parser.parse_args()))
