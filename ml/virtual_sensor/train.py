import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.virtual_sensor.dataset import load_scenario_data
from ml.virtual_sensor.features import FeatureTransformer, BASIC_FEATURE_COLUMNS
from ml.virtual_sensor.splits import BlockTemporalSplit, MultiSeasonTemporalSplit
from ml.virtual_sensor.scoring import compute_residuals, calibrate_thresholds
from ml.virtual_sensor.schemas import ModelMetadata, ThresholdConfig, PersistenceFilterConfig

def train_virtual_sensor(
    scenario_id: str = "sc_bd7fe667fc33",
    model_id: str = "vs-sa-temp-v2",
    model_type: str = "lightgbm",
    output_dir: str = "models",
    multiseason: bool = True
) -> ModelMetadata:
    print(f"--- Training Virtual Sensor: {model_id} ({model_type}) [MultiSeason={multiseason}] ---")
    df, scenario = load_scenario_data(scenario_id)
    print(f"Loaded scenario {scenario_id} ({scenario.name}): {len(df)} records")

    # Guard: Target leakage check
    if "SA_TEMP" in BASIC_FEATURE_COLUMNS:
        raise ValueError("CRITICAL ERROR: SA_TEMP detected in BASIC_FEATURE_COLUMNS! Target leakage prohibited.")

    time_col = "Datetime" if "Datetime" in df.columns else df.columns[0]

    # Split: Multi-season or Block temporal
    if multiseason and len(df) > 300 * 1440:
        splitter = MultiSeasonTemporalSplit()
        df_train, df_val, df_test, season_tests = splitter.split_annual(df)
        split_hash = splitter.get_split_hash()
        train_range = f"Multi-season 4x9d: 51,840 min"
        val_range = f"Multi-season 4x2d: 11,520 min"
        test_range = f"Multi-season 4x3d: 17,280 min"
    else:
        splitter = BlockTemporalSplit(train_days=9, val_days=2)
        df_train, df_val, df_test = splitter.split(df)
        split_hash = splitter.get_split_hash()
        train_range = f"{df_train[time_col].iloc[0]} to {df_train[time_col].iloc[-1]}"
        val_range = f"{df_val[time_col].iloc[0]} to {df_val[time_col].iloc[-1]}"
        test_range = f"{df_test[time_col].iloc[0]} to {df_test[time_col].iloc[-1]}"

    print(f"Split sizes: Train={len(df_train)} | Val={len(df_val)} | Held-out Test={len(df_test)}")

    # Feature transformation
    transformer = FeatureTransformer(feature_cols=BASIC_FEATURE_COLUMNS, target_col="SA_TEMP")
    transformer.fit(df_train)

    X_train, y_train, op_train = transformer.transform(df_train)
    X_val, y_val, op_val = transformer.transform(df_val)

    # Filter by operational gating (fan running)
    train_mask = op_train & y_train.notna()
    X_train_op = X_train[train_mask]
    y_train_op = y_train[train_mask]

    val_mask = op_val & y_val.notna()
    X_val_op = X_val[val_mask]
    y_val_op = y_val[val_mask]

    print(f"Operating training points: {len(X_train_op)} / {len(X_train)}")
    print(f"Operating validation points: {len(X_val_op)} / {len(X_val)}")

    # Model training
    hyperparams = {}
    if model_type == "lightgbm":
        hyperparams = {
            "n_estimators": 100,
            "learning_rate": 0.03,
            "max_depth": 4,
            "num_leaves": 15,
            "min_child_samples": 40,
            "random_state": 42,
            "objective": "regression",
            "verbose": -1
        }
        regressor = lgb.LGBMRegressor(**hyperparams)
    elif model_type == "ridge":
        hyperparams = {"alpha": 1.0, "random_state": 42}
        regressor = Ridge(**hyperparams)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")

    regressor.fit(X_train_op, y_train_op)

    # Validation evaluation
    y_val_pred_op = regressor.predict(X_val_op)
    val_mae = float(mean_absolute_error(y_val_op, y_val_pred_op))
    val_rmse = float(np.sqrt(mean_squared_error(y_val_op, y_val_pred_op)))
    val_r2 = float(r2_score(y_val_op, y_val_pred_op))

    print(f"Validation Metrics on Operating Points:")
    print(f"  MAE : {val_mae:.4f} °C")
    print(f"  RMSE: {val_rmse:.4f} °C")
    print(f"  R^2 : {val_r2:.4f}")

    # Threshold calibration
    y_val_full_pred = regressor.predict(X_val)
    _, abs_res_val = compute_residuals(y_val, y_val_full_pred)
    thresholds = calibrate_thresholds(abs_res_val, op_val)
    print(f"Calibrated Thresholds (Validation Normal):")
    print(f"  3-Sigma : {thresholds.three_sigma:.3f} °C")
    print(f"  Q95     : {thresholds.q95:.3f} °C")
    print(f"  MAD     : {thresholds.mad:.3f} °C")
    print(f"  Q99     : {thresholds.q99:.3f} °C")

    # Save artifacts
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    model_file = out_path / f"{model_id}.joblib"
    transformer_file = out_path / f"{model_id}_transformer.joblib"
    meta_file = out_path / f"{model_id}_metadata.json"

    joblib.dump(regressor, model_file)
    joblib.dump(transformer, transformer_file)

    meta = ModelMetadata(
        model_id=model_id,
        name=f"Virtual Sensor SA_TEMP v2 Multi-Season ({model_type.upper()})" if multiseason else f"Virtual Sensor SA_TEMP ({model_type.upper()})",
        description=f"Многосезонный виртуальный датчик приточной температуры SA_TEMP ({model_type}, Basic set)" if multiseason else f"Виртуальный датчик приточной температуры SA_TEMP ({model_type})",
        model_type=model_type,
        target="SA_TEMP",
        target_unit="degC",
        features=BASIC_FEATURE_COLUMNS,
        feature_units={
            "MA_TEMP": "degC",
            "OA_TEMP": "degC",
            "RA_TEMP": "degC",
            "CHWC_VLV_DM": "ratio_0_1",
            "OA_DMPR_DM": "ratio_0_1",
            "SF_SPD_DM": "binary_0_1",
            "SA_TEMPSPT": "degC"
        },
        operational_gating_feature="SF_SPD_DM",
        train_scenario_id=scenario_id,
        train_range=train_range,
        val_range=val_range,
        test_range=test_range,
        split_hash=split_hash,
        random_state=42,
        hyperparameters=hyperparams,
        validation_metrics={
            "mae_degC": round(val_mae, 4),
            "rmse_degC": round(val_rmse, 4),
            "r2": round(val_r2, 4)
        },
        thresholds=thresholds,
        persistence_filter=PersistenceFilterConfig(k=10, n=15),
        library_versions={
            "lightgbm": lgb.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__
        },
        created_at=datetime.now(timezone.utc).isoformat()
    )

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"Saved artifacts to {out_path}:")
    print(f"  Model:       {model_file}")
    print(f"  Transformer: {transformer_file}")
    print(f"  Metadata:    {meta_file}")
    return meta

def main():
    parser = argparse.ArgumentParser(description="Обучение виртуального датчика SA_TEMP")
    parser.add_argument("--scenario-id", type=str, default="sc_bd7fe667fc33", help="Сценарий обучения (полный год нормы LBNL)")
    parser.add_argument("--model-id", type=str, default="vs-sa-temp-v2", help="ID модели")
    parser.add_argument("--model-type", type=str, default="lightgbm", choices=["lightgbm", "ridge"])
    parser.add_argument("--output-dir", type=str, default="models", help="Каталог сохранения")
    parser.add_argument("--no-multiseason", action="store_true", help="Отключить многосезонный режим")
    args = parser.parse_args()

    train_virtual_sensor(
        scenario_id=args.scenario_id,
        model_id=args.model_id,
        model_type=args.model_type,
        output_dir=args.output_dir,
        multiseason=not args.no_multiseason
    )

if __name__ == "__main__":
    main()
