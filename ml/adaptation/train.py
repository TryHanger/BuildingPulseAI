"""
Training pipeline for CSIRO AHU9 domain adaptation models.
Trains C1, C2, A1, L1, L2 models strictly on the clean healthy Train Local split,
evaluates on Validation Local, calibrates alarm thresholds, and saves
versioned artifacts into models/ and research/runs/.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib

from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
from ml.adaptation.data import (
    load_csiro_dataset,
    extract_adaptation_matrices,
    LOCAL_ADAPTATION_FEATURES
)
from ml.adaptation.splits import CSIROTemporalSplitter
from ml.adaptation.calibrators import (
    ConstantBiasCalibrator,
    AffineCalibrator,
    ResidualRidgeCalibrator,
    LocalRidgeModel,
    LocalLightGBMModel,
    PhysicalBaselinePredictor
)
from ml.adaptation.metrics import compute_regression_metrics

def train_adaptation_models(scenario_id: str = "sc_89e2c6028b4f"):
    print("==================================================================")
    print(" BUILDINGPULSE AI — CSIRO AHU9 DOMAIN ADAPTATION TRAINING (GATE 2)")
    print("==================================================================\n")

    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = Path("research/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    print(f"Loading scenario '{scenario_id}' and fault experiments...")
    df, df_exp = load_csiro_dataset(scenario_id)

    # 2. Split strictly chronologically
    splitter = CSIROTemporalSplitter(embargo_minutes=60)
    splits = splitter.split(df, df_exp)

    train_idx = splits["train"]["clean_operating_indices"]
    val_idx = splits["val"]["clean_operating_indices"]
    print(f"  Train clean healthy operating points: {len(train_idx)}")
    print(f"  Validation clean healthy operating points: {len(val_idx)}")

    # 3. Source model inference (vs-sa-temp-v2)
    print("\nLoading source model (vs-sa-temp-v2)...")
    engine = VirtualSensorInferenceEngine()
    source_model, source_trans, source_meta = engine.load_model("vs-sa-temp-v2")

    # Features for source model
    X_src_all, _, _ = source_trans.transform(df)
    y_src_pred_all = source_model.predict(X_src_all)

    # 4. Local feature matrices (strictly sanitized, no target or labels)
    X_local_all, y_true_all, _ = extract_adaptation_matrices(df)

    y_true_train = y_true_all.iloc[train_idx].values
    y_src_train = y_src_pred_all[train_idx]
    X_train = X_local_all.iloc[train_idx]

    y_true_val = y_true_all.iloc[val_idx].values
    y_src_val = y_src_pred_all[val_idx]
    X_val = X_local_all.iloc[val_idx]

    # Evaluate Source Model Z0 on Val
    z0_val_metrics = compute_regression_metrics(y_true_val, y_src_val)
    print(f"  Source Model Z0 on Validation: MAE={z0_val_metrics['mae_degC']} °C, Bias={z0_val_metrics['mean_bias_degC']:+.4f} °C, R2={z0_val_metrics['r2']}")

    # 5. Fit Adaptation Models on Train
    print("\nFitting adaptation models on clean train data...")

    # C1: Constant Bias
    c1_model = ConstantBiasCalibrator()
    c1_model.fit(y_true_train, y_src_train)
    print(f"  [C1 Constant Bias] Fitted bias: {c1_model.bias_:+.4f} °C")

    # C2: Affine Calibrator
    c2_model = AffineCalibrator(alpha=1.0)
    c2_model.fit(y_true_train, y_src_train)
    print(f"  [C2 Affine] Fitted slope: {c2_model.slope_:.4f}, intercept: {c2_model.intercept_:+.4f} °C")

    # A1: Residual Ridge
    a1_model = ResidualRidgeCalibrator(alpha=10.0)
    a1_model.fit(X_train, y_true_train, y_src_train)
    print(f"  [A1 Residual Ridge] Fitted on {len(a1_model.feature_names_)} features")

    # L1: Local Ridge
    l1_model = LocalRidgeModel(alpha=10.0)
    l1_model.fit(X_train, y_true_train)
    print(f"  [L1 Local Ridge] Fitted on {len(l1_model.feature_names_)} features")

    # L2: Local LightGBM
    l2_model = LocalLightGBMModel(n_estimators=50, max_depth=3, num_leaves=7, learning_rate=0.05, random_state=42)
    l2_model.fit(X_train, y_true_train)
    print(f"  [L2 Local LightGBM] Fitted on {len(l2_model.feature_names_)} features")

    # B0: Physical Baseline
    b0_model = PhysicalBaselinePredictor()

    # 6. Evaluate on Validation and Calibrate Thresholds
    print("\nEvaluating on independent Validation Local and calibrating thresholds...")
    models_dict = {
        "Z0_source": (lambda X, ys: ys, "OUT_OF_DOMAIN_UNVALIDATED"),
        "B0_physical": (lambda X, ys: b0_model.predict(X), "LOCALLY_EVALUATED"),
        "C1_constant_bias": (lambda X, ys: c1_model.predict(ys), "LOCALLY_EVALUATED"),
        "C2_affine": (lambda X, ys: c2_model.predict(ys), "LOCALLY_EVALUATED"),
        "A1_residual_ridge": (lambda X, ys: a1_model.predict(X, ys), "LOCALLY_EVALUATED"),
        "L1_local_ridge": (lambda X, ys: l1_model.predict(X), "LOCALLY_EVALUATED"),
        "L2_local_lgbm": (lambda X, ys: l2_model.predict(X), "LOCALLY_EVALUATED")
    }

    val_results = {}
    calibrated_thresholds = {}

    for name, (pred_func, status) in models_dict.items():
        y_val_pred = pred_func(X_val, y_src_val)
        val_met = compute_regression_metrics(y_true_val, y_val_pred)

        # Calibrate residual thresholds on validation errors
        val_res = np.abs(y_true_val - y_val_pred)
        t_3sigma = float(np.mean(val_res) + 3.0 * np.std(val_res))
        t_q95 = float(np.percentile(val_res, 95))
        t_mad = float(np.median(np.abs(val_res - np.median(val_res))))

        calibrated_thresholds[name] = {
            "three_sigma": round(t_3sigma, 4),
            "q95": round(t_q95, 4),
            "mad": round(t_mad, 4)
        }
        val_results[name] = {
            "status": status,
            "metrics": val_met,
            "thresholds": calibrated_thresholds[name]
        }
        print(f"  {name:<18} Val MAE: {val_met['mae_degC']:.4f} °C, RMSE: {val_met['rmse_degC']:.4f} °C, Bias: {val_met['mean_bias_degC']:+.4f} °C, R2: {val_met['r2']}, 3sigma_th: {t_3sigma:.3f} °C")

    # 7. Persist Model Artifacts and Metadata
    print("\nPersisting versioned model artifacts...")
    artifacts = [
        ("csiro-ahu9-bias-v1", c1_model, "Constant Bias Corrector", "C1", {
            "fitted_bias_degC": c1_model.bias_
        }),
        ("csiro-ahu9-affine-v1", c2_model, "Affine Calibrator", "C2", {
            "slope": c2_model.slope_,
            "intercept_degC": c2_model.intercept_
        }),
        ("csiro-ahu9-residual-ridge-v1", a1_model, "Residual Ridge Corrector", "A1", {
            "alpha": a1_model.alpha,
            "features": a1_model.feature_names_
        }),
        ("csiro-ahu9-local-ridge-v1", l1_model, "Local Ridge Model", "L1", {
            "alpha": l1_model.alpha,
            "features": l1_model.feature_names_
        }),
        ("csiro-ahu9-local-lgbm-v1", l2_model, "Local LightGBM Model", "L2", {
            "n_estimators": 50,
            "max_depth": 3,
            "num_leaves": 7,
            "features": l2_model.feature_names_
        })
    ]

    saved_files = []
    for model_id, obj, desc, strat_code, extra_meta in artifacts:
        joblib_path = models_dir / f"{model_id}.joblib"
        joblib.dump(obj, joblib_path)

        meta = {
            "model_id": model_id,
            "name": f"CSIRO AHU9 Adaptation: {desc}",
            "description": desc,
            "strategy_code": strat_code,
            "model_type": "adaptation_calibrator",
            "target_domain": "CSIRO_AHU9",
            "source_kind": "REAL_FIELD_BMS",
            "target": "SA_TEMP",
            "target_unit": "degC",
            "features": extra_meta.get("features", ["f_source(X)"]),
            "status": "LOCALLY_EVALUATED",
            "prediction_validity": "REGRESSION_ONLY_HELDOUT",
            "fault_localization_validity": "NOT_VALIDATED",
            "train_sample_count": len(train_idx),
            "val_sample_count": len(val_idx),
            "validation_metrics": val_results.get(f"{strat_code.lower()}_{desc.lower().replace(' ', '_')}", val_results.get(strat_code, {})).get("metrics"),
            "calibrated_thresholds": calibrated_thresholds.get(f"{strat_code.lower()}_{desc.lower().replace(' ', '_')}", {}),
            "persistence_filter": {"k": 10, "n": 15},
            "parameters": extra_meta,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Match threshold key properly
        for k in calibrated_thresholds:
            if strat_code.lower() in k.lower():
                meta["validation_metrics"] = val_results[k]["metrics"]
                meta["calibrated_thresholds"] = val_results[k]["thresholds"]
                break

        meta_path = models_dir / f"{model_id}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        saved_files.append(str(joblib_path))
        print(f"  Saved {joblib_path} and {meta_path}")

    # 8. Persist Training Run Manifest
    train_manifest = {
        "run_id": "stage6_train_csiro_adaptation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": scenario_id,
        "source_model_id": "vs-sa-temp-v2",
        "splits_summary": {
            "train_points": len(train_idx),
            "val_points": len(val_idx),
            "embargo_minutes": 60
        },
        "validation_comparison": val_results,
        "artifacts_saved": saved_files
    }
    train_manifest_path = runs_dir / "stage6_csiro_adaptation_train.json"
    with open(train_manifest_path, "w", encoding="utf-8") as f:
        json.dump(train_manifest, f, indent=2, ensure_ascii=False)
    print(f"\nSaved training manifest: {train_manifest_path}")

    return train_manifest

if __name__ == "__main__":
    train_adaptation_models()
