import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import joblib
import numpy as np
import pandas as pd

from backend.app.core.config import settings
from ml.virtual_sensor.dataset import load_scenario_data
from ml.virtual_sensor.schemas import (
    ModelMetadata,
    ScenarioPredictionResult,
    PredictionPoint,
    ThresholdConfig,
    PersistenceFilterConfig
)
from ml.virtual_sensor.scoring import compute_residuals, apply_persistence_filter, count_alarm_episodes

class VirtualSensorInferenceEngine:
    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or (Path(__file__).resolve().parent.parent.parent / "models")

    def load_model(self, model_id: str):
        model_file = self.models_dir / f"{model_id}.joblib"
        transformer_file = self.models_dir / f"{model_id}_transformer.joblib"
        meta_file = self.models_dir / f"{model_id}_metadata.json"

        if not model_file.exists():
            raise FileNotFoundError(f"Model file {model_file} not found. Status: MODEL_NOT_TRAINED")
        if not meta_file.exists():
            raise FileNotFoundError(f"Metadata file {meta_file} not found")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta_dict = json.load(f)

        is_adaptation = (
            model_id.startswith("csiro-")
            or meta_dict.get("source_kind") == "REAL_FIELD_BMS"
            or meta_dict.get("target_domain") == "CSIRO_AHU9"
            or meta_dict.get("model_type") in ["adaptation_calibrator", "ridge_direct", "lgbm_direct", "residual_ridge"]
        )

        transformer = None
        if transformer_file.exists():
            transformer = joblib.load(transformer_file)
        elif not is_adaptation:
            raise FileNotFoundError(f"Transformer file {transformer_file} not found")

        model = joblib.load(model_file)

        # Build meta with safe defaults for CSIRO models
        if "thresholds" not in meta_dict and "calibrated_thresholds" in meta_dict:
            ct = meta_dict["calibrated_thresholds"]
            meta_dict["thresholds"] = {
                "q95": ct.get("q95", 1.83),
                "q99": ct.get("q99", ct.get("three_sigma", 3.0)),
                "three_sigma": ct.get("three_sigma", 3.0),
                "mad": ct.get("mad", 0.2),
            }
        elif "thresholds" not in meta_dict:
            meta_dict["thresholds"] = {
                "q95": 1.83,
                "q99": 3.0,
                "three_sigma": 3.0,
                "mad": 0.2
            }

        meta = ModelMetadata(**meta_dict)
        return model, transformer, meta

    def list_available_models(self) -> List[Dict[str, Any]]:
        results = []
        if not self.models_dir.exists():
            return results
        for meta_file in sorted(self.models_dir.glob("*_metadata.json")):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except Exception:
                pass
        return results

    def predict_scenario(
        self,
        scenario_id: str,
        model_id: str = "vs-sa-temp-v1",
        threshold_policy: str = "three_sigma",
        max_points: Optional[int] = None
    ) -> ScenarioPredictionResult:
        model, transformer, meta = self.load_model(model_id)
        df, scenario = load_scenario_data(scenario_id)

        is_csiro_model = (
            model_id.startswith("csiro-")
            or (meta.target_domain and "CSIRO" in meta.target_domain)
            or meta.source_kind == "REAL_FIELD_BMS"
        )
        scenario_source_kind = scenario.dataset.source_kind if (scenario and scenario.dataset) else "UNKNOWN"
        is_csiro_scenario = (scenario_source_kind == "REAL_FIELD_BMS" or "csiro" in scenario.name.lower())

        # Enforce domain compatibility guard
        if is_csiro_model and not is_csiro_scenario:
            raise ValueError(
                f"Модель '{model_id}' откалибрована для натурного датасета CSIRO AHU9 (REAL_FIELD_BMS) "
                f"и несовместима со сценарием '{scenario.name}' ({scenario_source_kind}). "
                f"Для данного сценария выберите модель симулятора LBNL (vs-sa-temp-v1 / vs-sa-temp-v2) "
                f"или откройте сценарий CSIRO на вкладке «Исследования». Status: INCOMPATIBLE_DATASET_DOMAIN"
            )

        if is_csiro_model:
            from ml.adaptation.data import estimate_physical_mixed_air_temp, extract_adaptation_matrices
            df_work = df.copy()
            if "MA_TEMP" not in df_work.columns:
                df_work["MA_TEMP"] = estimate_physical_mixed_air_temp(df_work)

            if model_id in ["csiro-ahu9-bias-v1", "csiro-ahu9-affine-v1", "csiro-ahu9-residual-ridge-v1"]:
                src_model, src_trans, _ = self.load_model("vs-sa-temp-v2")
                X_src, _, _ = src_trans.transform(df_work)
                y_source = src_model.predict(X_src)
                if model_id in ["csiro-ahu9-bias-v1", "csiro-ahu9-affine-v1"]:
                    y_pred = model.predict(y_source)
                else:
                    X_local, _, _ = extract_adaptation_matrices(df_work)
                    y_pred = model.predict(X_local, y_source)
            else:
                X_local, _, _ = extract_adaptation_matrices(df_work)
                y_pred = model.predict(X_local)

            operating_mask = df["SF_SPD_DM"] >= 0.5 if "SF_SPD_DM" in df.columns else pd.Series(True, index=df.index)
            y_actual = df["SA_TEMP"] if "SA_TEMP" in df.columns else None
        else:
            if transformer is None:
                raise ValueError(f"Model '{model_id}' lacks feature transformer.")
            missing = [c for c in transformer.feature_cols if c not in df.columns]
            if missing:
                if missing == ["MA_TEMP"] and "OA_TEMP" in df.columns and "RA_TEMP" in df.columns:
                    from ml.adaptation.data import estimate_physical_mixed_air_temp
                    df = df.copy()
                    df["MA_TEMP"] = estimate_physical_mixed_air_temp(df)
                    missing = []
                if missing:
                    raise ValueError(f"Scenario '{scenario_id}' lacks required features: {missing}. Status: MODEL_INCOMPATIBLE_CHANNELS")

            X, y_actual, operating_mask = transformer.transform(df)
            y_pred = model.predict(X)

        time_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        timestamps = df[time_col].astype(str).tolist()

        # Residuals
        if y_actual is not None:
            signed_res, abs_res = compute_residuals(y_actual, y_pred)
        else:
            signed_res = pd.Series(0.0, index=df.index)
            abs_res = pd.Series(0.0, index=df.index)

        # Pick threshold value
        thresh_cfg: ThresholdConfig = meta.thresholds
        if threshold_policy == "q95":
            thresh_val = thresh_cfg.q95
        elif threshold_policy == "q99":
            thresh_val = thresh_cfg.q99
        elif threshold_policy == "mad":
            thresh_val = thresh_cfg.mad
        else:
            thresh_val = thresh_cfg.three_sigma

        # Persistence alarm filter
        alarm_mask = apply_persistence_filter(
            abs_residuals=abs_res,
            threshold=thresh_val,
            operating_mask=operating_mask,
            config=meta.persistence_filter
        )

        alarm_episodes = count_alarm_episodes(alarm_mask)
        total_alarm_pts = int(alarm_mask.sum())
        total_op_pts = int(operating_mask.sum())

        # Select indices to construct points for
        if max_points and max_points > 0 and len(df) > max_points:
            step = max(1, len(df) // max_points)
            # Sample indices: every step-th point OR points in alarm
            alarm_indices = set(np.where(alarm_mask.values)[0])
            sampled_indices = set(range(0, len(df), step))
            chosen_indices = sorted(alarm_indices.union(sampled_indices))
        else:
            chosen_indices = range(len(df))

        # Build prediction points only for chosen indices
        final_points: List[PredictionPoint] = []
        for i in chosen_indices:
            is_op = bool(operating_mask.iloc[i])
            is_al = bool(alarm_mask.iloc[i])
            act = float(round(y_actual.iloc[i], 2)) if y_actual is not None and not np.isnan(y_actual.iloc[i]) else None
            pred = float(round(y_pred[i], 2))
            s_res = float(round(signed_res.iloc[i], 2)) if y_actual is not None else None
            a_res = float(round(abs_res.iloc[i], 2)) if y_actual is not None else None

            status = "OK"
            if not is_op:
                status = "AHU_OFF"
            elif is_al:
                status = "ANOMALY_ALERT"

            final_points.append(PredictionPoint(
                timestamp=timestamps[i],
                actual=act,
                predicted=pred,
                residual_signed=s_res,
                residual_abs=a_res,
                threshold=round(thresh_val, 2),
                is_operating=is_op,
                is_alarm=is_al,
                status=status
            ))

        # Compute summary metrics if actual is available
        metrics = None
        if y_actual is not None and total_op_pts > 0:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            y_act_op = y_actual[operating_mask].dropna()
            y_pred_op = y_pred[operating_mask.values][:len(y_act_op)]
            if len(y_act_op) > 0:
                metrics = {
                    "mae_degC": round(float(mean_absolute_error(y_act_op, y_pred_op)), 4),
                    "rmse_degC": round(float(np.sqrt(mean_squared_error(y_act_op, y_pred_op))), 4),
                    "r2": round(float(r2_score(y_act_op, y_pred_op)), 4)
                }

        return ScenarioPredictionResult(
            scenario_id=scenario_id,
            model_id=model_id,
            target="SA_TEMP",
            unit="degC",
            total_points=len(df),
            operating_points=total_op_pts,
            alarm_points=total_alarm_pts,
            alarm_episodes_count=alarm_episodes,
            threshold_policy=threshold_policy,
            threshold_value=thresh_val,
            points=final_points,
            metrics=metrics
        )
