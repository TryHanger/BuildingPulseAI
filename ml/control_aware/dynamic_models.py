"""
Dynamic Models and Scale Calibration for Stage 8B.

Includes:
1. DynamicRidgeControlModel: Fits Ridge regressor on exogenous dynamic features.
2. DynamicThermalARXModel: Fits ARX thermal model predicting SA_TEMP from past inputs.
3. RobustRegimeScaler: Computes regime-specific scale estimators (sigma, MAD, IQR)
   and standardizes residuals per operating regime.
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LinearRegression


class DynamicRidgeControlModel:
    """
    Dynamic Ridge model for expected control effort u_hat.
    Predicts normal expected valve command based on exogenous conditions and past dynamics.
    """
    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha
        self.model = Ridge(alpha=alpha)
        self.feature_names_: List[str] = []
        self.is_fitted: bool = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DynamicRidgeControlModel":
        self.feature_names_ = list(X.columns)
        self.model.fit(X.values, y.values)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet.")
        preds = self.model.predict(X[self.feature_names_].values)
        # Actuator commands are physically bounded in [0.0, 1.0]
        return np.clip(preds, 0.0, 1.0)


class DynamicThermalARXModel:
    """
    Dynamic ARX thermal model for Supply Air Temperature (SA_TEMP).
    Predicts SA_TEMP from exogenous inputs and historical lags.
    """
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.model = Ridge(alpha=alpha)
        self.feature_names_: List[str] = []
        self.is_fitted: bool = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DynamicThermalARXModel":
        self.feature_names_ = list(X.columns)
        self.model.fit(X.values, y.values)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet.")
        return self.model.predict(X[self.feature_names_].values)


class RobustRegimeScaler:
    """
    Calibrates regime-dependent scale statistics (sigma, MAD) on validation
    normal data to prevent false alarms during unexcited or transitional regimes.
    """
    def __init__(self, min_samples: int = 30, min_sigma: float = 1e-4):
        self.min_samples = min_samples
        self.min_sigma = min_sigma
        self.regime_stats_: Dict[str, Dict[str, float]] = {}
        self.global_stats_: Dict[str, float] = {}

    def fit(self, residuals: np.ndarray, regimes: pd.Series) -> "RobustRegimeScaler":
        res_series = pd.Series(residuals, index=regimes.index)

        # Global statistics
        glob_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 1.0
        glob_mad = float(np.median(np.abs(residuals - np.median(residuals))))
        self.global_stats_ = {
            "std": max(glob_std, self.min_sigma),
            "mad": max(glob_mad, self.min_sigma),
            "count": len(residuals)
        }

        # Per-regime statistics
        for reg in np.unique(regimes):
            sub_res = res_series[regimes == reg].values
            if len(sub_res) >= self.min_samples:
                r_std = float(np.std(sub_res, ddof=1))
                r_mad = float(np.median(np.abs(sub_res - np.median(sub_res))))
                self.regime_stats_[reg] = {
                    "std": max(r_std, self.min_sigma),
                    "mad": max(r_mad, self.min_sigma),
                    "count": len(sub_res)
                }
            else:
                # Fallback to global
                self.regime_stats_[reg] = self.global_stats_.copy()

        return self

    def transform(self, residuals: np.ndarray, regimes: pd.Series, use_mad: bool = False) -> np.ndarray:
        """
        Standardizes absolute residuals by the regime-specific scale.
        """
        stat_key = "mad" if use_mad else "std"
        z_scores = np.empty(len(residuals), dtype=float)

        for i, reg in enumerate(regimes):
            scale = self.regime_stats_.get(reg, self.global_stats_)[stat_key]
            z_scores[i] = np.abs(residuals[i]) / scale

        return z_scores
