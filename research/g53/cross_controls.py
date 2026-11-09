"""Independent 5wk reconciliation and descriptive context. Never reads 1wk data."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from research.g52.verify_experiment import COOL, END, FAN, OAT, OCCUPIED, OWB, SP, START, TIME, independent

PROBES = (
    "Outdoor Air Mass Flow Rate (kg/s)",
    "Supply Air Mass Flow Rate (kg/s)",
    "Measured AHU Supply Air Duct Static Pressure (Pa)",
    "Cooling Coil Heat Transfer Rate (W)",
    "AHU Supply Air Fan Speed Control Signal (fraction, 0: fan speed should be 0% to 1:fan speed should be 100%)",
)
BINS = ["[0.20,0.50)", "[0.50,0.80)", "[0.80,0.95)", "[0.95,1.00)", "1.00"]


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "comparison", "auditor", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text())
    audit = json.loads(args.auditor.read_text())["scenario_results"]
    output = {"scope": "EXPLORATORY_POST_HOC", "runs": {}}
    nominal, nominal_applicable, nominal_exceeds = None, None, None
    for run in comparison["runs"]:
        file = args.source / run["source_file"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == run["source_sha256"]
        frame = pd.read_csv(file, float_precision="round_trip")
        assert len(frame) == 10081 and frame[TIME].diff().dropna().eq(300).all()
        assert frame[[OAT, OWB]].notna().all().all()
        time = frame[TIME]
        before, active, after = frame[time < START], frame[(time >= START) & (time < END)], frame[time >= END]
        summaries = {}
        for phase, part in zip(("pre", "active", "post"), (before, active, after), strict=True):
            summary, (applicable, _, exceeds, _) = independent(part)
            assert summary == audit[file.stem][phase], (run["scenario"], phase)
            summaries[phase] = summary
            if phase == "active":
                valid, point_exceeds = applicable, exceeds
        assert {k: v for k, v in run["summary"].items() if k != "period"} == summaries["active"]
        selected = active.loc[valid, COOL]
        distribution = pd.cut(selected, [0.20, 0.50, 0.80, 0.95, 1, 1.01], labels=BINS, right=False)
        assert distribution.value_counts().to_dict() == run["cooling_command_bins"]
        if nominal is None:
            nominal, nominal_applicable, nominal_exceeds = frame, valid, point_exceeds
        intersection = nominal_applicable & valid
        output["runs"][run["scenario"]] = {
            "summaries": summaries,
            "applicable_cooling_command_bins": run["cooling_command_bins"],
            "active_regime_intersection": {
                "common_applicable": int(intersection.sum()),
                "nominal_exceeds": int((intersection & nominal_exceeds).sum()),
                "run_exceeds": int((intersection & point_exceeds).sum()),
            },
            "control_context": {
                "median_on_applicable": active.loc[valid, list(PROBES)].median().to_dict(),
                "median_on_exceedances": active.loc[point_exceeds, list(PROBES)].median().to_dict(),
                "pre_rows_not_equal_to_nominal": int(before.ne(nominal.loc[before.index]).any(axis=1).sum()),
                "nominal_mismatches": {column: int(frame[column].ne(nominal[column]).sum())
                                       for column in (OAT, OWB, OCCUPIED, FAN, SP)},
            },
        }
    assert output["runs"]["VALVE_CLOSED"]["control_context"]["pre_rows_not_equal_to_nominal"] == 59
    assert output["runs"]["VALVE_CLOSED"]["summaries"]["pre"]["point_exceedances"] == output["runs"]["NOMINAL"]["summaries"]["pre"]["point_exceedances"]
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print("PASS independent parity for 12 period summaries and 4 command distributions, including pre-injection placebo.")


if __name__ == "__main__":
    main()
