import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
from ml.virtual_sensor.dataset import load_scenario_data
from ml.virtual_sensor.splits import BlockTemporalSplit
from ml.virtual_sensor.schemas import ThresholdConfig
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def run_evaluation(output_dir: str = "research/runs"):
    print("=================================================================")
    print(" BUILDINGPULSE AI — VIRTUAL SENSOR EVALUATION (STAGE 2) ")
    print("=================================================================\n")

    engine = VirtualSensorInferenceEngine()

    # Load models
    models = ["vs-sa-temp-v1", "vs-sa-temp-baseline-ridge"]

    # 1. EVALUATION ON HELD-OUT NORMAL TEST SPLIT
    normal_sc_id = "sc_3556175a5da2"
    df_norm, _ = load_scenario_data(normal_sc_id)
    splitter = BlockTemporalSplit(train_days=9, val_days=2)
    _, _, df_test = splitter.split(df_norm)

    print(f"1. Held-out Normal Test Split (Days 12-14): {len(df_test)} minutes\n")

    normal_results = {}
    for m_id in models:
        model, transformer, meta = engine.load_model(m_id)
        X_test, y_test, op_test = transformer.transform(df_test)
        y_pred = model.predict(X_test)

        # Operating points only
        mask = op_test & y_test.notna()
        mae = float(mean_absolute_error(y_test[mask], y_pred[mask.values]))
        rmse = float(np.sqrt(mean_squared_error(y_test[mask], y_pred[mask.values])))
        r2 = float(r2_score(y_test[mask], y_pred[mask.values]))

        # Residuals & false alarms with 3-sigma policy
        thresh = meta.thresholds.three_sigma
        abs_res = (y_test - y_pred).abs()
        from ml.virtual_sensor.scoring import apply_persistence_filter, count_alarm_episodes
        alarms = apply_persistence_filter(abs_res, thresh, op_test, meta.persistence_filter)
        episodes = count_alarm_episodes(alarms)

        normal_results[m_id] = {
            "model_type": meta.model_type,
            "test_points": int(mask.sum()),
            "mae_degC": round(mae, 4),
            "rmse_degC": round(rmse, 4),
            "r2": round(r2, 4),
            "threshold_3sigma_degC": round(thresh, 3),
            "false_alarm_points": int(alarms.sum()),
            "false_alarm_episodes": episodes
        }

    print("Table 1: Held-out Normal Performance (Days 12-14)")
    print("| Model ID | Architecture | Test Points | MAE (deg C) | RMSE (deg C) | R^2 | Threshold 3-sigma | False Alarm Pts | False Episodes |")
    print("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for mid, res in normal_results.items():
        print(f"| `{mid}` | {res['model_type']} | {res['test_points']} | {res['mae_degC']} | {res['rmse_degC']} | {res['r2']} | {res['threshold_3sigma_degC']} deg C | {res['false_alarm_points']} | {res['false_alarm_episodes']} |")
    print()

    # 2. EVALUATION ON REAL LBNL FAULT SCENARIOS
    fault_scenarios = [
        {
            "scenario_id": "sc_22370df7e61a",
            "name": "coi_bias_2_annual (Supply Air Sensor Bias +2 deg C)",
            "fault_family": "SENSOR_BIAS",
            "intensity": "+2.0 deg C on SA_TEMP"
        },
        {
            "scenario_id": "sc_276968373895",
            "name": "coi_stuck_025_annual (Cooling Coil Valve Stuck 25%)",
            "fault_family": "VALVE_STUCK",
            "intensity": "25% stuck (CHWC_VLV=0.25)"
        },
        {
            "scenario_id": "sc_1e3ca900a8d7",
            "name": "damper_stuck_025_annual (OA Damper Stuck 25%)",
            "fault_family": "DAMPER_STUCK",
            "intensity": "25% stuck (OA_DMPR=0.25)"
        }
    ]

    fault_results = []
    primary_model = "vs-sa-temp-v1"

    print("2. Evaluation on LBNL Injected Fault Scenarios (LightGBM vs-sa-temp-v1)")
    print("| Scenario | Fault Family | Intensity | Operating Pts | Mean Abs Residual (deg C) | Alarm Points | Detection Rate | Alarm Episodes |")
    print("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

    for f_info in fault_scenarios:
        df_f, sc = load_scenario_data(f_info["scenario_id"])
        # Use corresponding test window (last 3 days) for fair comparison
        df_f_test = df_f.iloc[splitter.train_points + splitter.val_points :].copy()

        model, transformer, meta = engine.load_model(primary_model)
        X_f, y_f, op_f = transformer.transform(df_f_test)
        y_f_pred = model.predict(X_f)

        mask_f = op_f & y_f.notna()
        abs_res_f = (y_f - y_f_pred).abs()
        mean_abs_res = float(abs_res_f[mask_f].mean())

        thresh = meta.thresholds.three_sigma
        alarms_f = apply_persistence_filter(abs_res_f, thresh, op_f, meta.persistence_filter)
        episodes_f = count_alarm_episodes(alarms_f)
        alarm_pts = int(alarms_f.sum())
        op_pts = int(mask_f.sum())
        det_rate = (alarm_pts / op_pts * 100.0) if op_pts > 0 else 0.0

        item = {
            "scenario_id": f_info["scenario_id"],
            "name": f_info["name"],
            "fault_family": f_info["fault_family"],
            "intensity": f_info["intensity"],
            "operating_points": op_pts,
            "mean_abs_residual_degC": round(mean_abs_res, 3),
            "alarm_points": alarm_pts,
            "detection_rate_pct": round(det_rate, 1),
            "alarm_episodes": episodes_f
        }
        fault_results.append(item)
        print(f"| {f_info['fault_family']} | {f_info['fault_family']} | {f_info['intensity']} | {op_pts} | {round(mean_abs_res, 3)} deg C | {alarm_pts} | {round(det_rate, 1)}% | {episodes_f} |")

    # Save run manifest
    run_manifest = {
        "run_id": f"eval_run_{int(datetime.now(timezone.utc).timestamp())}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "primary_model": primary_model,
        "baseline_model": "vs-sa-temp-baseline-ridge",
        "normal_held_out": normal_results,
        "fault_scenarios": fault_results
    }

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    manifest_path = out_p / "virtual_sensor_v1_evaluation.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2, ensure_ascii=False)

    print(f"\nRun manifest saved to {manifest_path}")
    return run_manifest

if __name__ == "__main__":
    run_evaluation()
