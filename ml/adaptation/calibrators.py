"""
Adaptation model architectures and calibrators for CSIRO AHU9.
Implements:
  - C1: ConstantBiasCalibrator (y_hat = f_source(x) + b)
  - C2: AffineCalibrator (y_hat = a * f_source(x) + b)
  - A1: ResidualRidgeCalibrator (y_hat = f_source(x) + Ridge(X))
  - L1: LocalRidgeModel (y_hat = Ridge(X) from scratch)
  - L2: LocalLightGBMModel (shallow decision tree from scratch)
  - B0: PhysicalBaselinePredictor (y_hat = MA_TEMP_EST from mixing thermodynamics)
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMRegressor

class ConstantBiasCalibrator:
    """Strategy C1: Constant bias correction b = mean(y - f_source(x))."""
    def __init__(self):
        self.bias_: float = 0.0
        self.is_fitted_: bool = False

    def fit(self, y_true: np.ndarray, y_source: np.ndarray) -> "ConstantBiasCalibrator":
        residuals = y_true - y_source
        self.bias_ = float(np.mean(residuals))
        self.is_fitted_ = True
        return self

    def predict(self, y_source: np.ndarray) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError("ConstantBiasCalibrator is not fitted.")
        return y_source + self.bias_

class AffineCalibrator:
    """Strategy C2: Affine calibration y_hat = a * f_source(x) + b."""
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.slope_: float = 1.0
        self.intercept_: float = 0.0
        self.is_fitted_: bool = False

    def fit(self, y_true: np.ndarray, y_source: np.ndarray) -> "AffineCalibrator":
        X_1d = y_source.reshape(-1, 1)
        reg = Ridge(alpha=self.alpha, fit_intercept=True)
        reg.fit(X_1d, y_true)
        self.slope_ = float(reg.coef_[0])
        self.intercept_ = float(reg.intercept_)
        self.is_fitted_ = True
        return self

    def predict(self, y_source: np.ndarray) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError("AffineCalibrator is not fitted.")
        return self.slope_ * y_source + self.intercept_

class ResidualRidgeCalibrator:
    """Strategy A1: Source prediction + Residual Ridge model."""
    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha
        self.scaler = StandardScaler()
        self.model = Ridge(alpha=self.alpha, fit_intercept=True)
        self.feature_names_: list = []
        self.is_fitted_: bool = False

    def fit(self, X: pd.DataFrame, y_true: np.ndarray, y_source: np.ndarray) -> "ResidualRidgeCalibrator":
        self.feature_names_ = list(X.columns)
        residuals = y_true - y_source
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, residuals)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame, y_source: np.ndarray) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError("ResidualRidgeCalibrator is not fitted.")
        X_scaled = self.scaler.transform(X[self.feature_names_])
        res_pred = self.model.predict(X_scaled)
        return y_source + res_pred

class LocalRidgeModel:
    """Strategy L1: Local-only Ridge regression from scratch."""
    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha
        self.scaler = StandardScaler()
        self.model = Ridge(alpha=self.alpha, fit_intercept=True)
        self.feature_names_: list = []
        self.is_fitted_: bool = False

    def fit(self, X: pd.DataFrame, y_true: np.ndarray) -> "LocalRidgeModel":
        self.feature_names_ = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y_true)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError("LocalRidgeModel is not fitted.")
        X_scaled = self.scaler.transform(X[self.feature_names_])
        return self.model.predict(X_scaled)

class LocalLightGBMModel:
    """Strategy L2: Local-only restricted LightGBM from scratch."""
    def __init__(
        self,
        n_estimators: int = 50,
        max_depth: int = 3,
        num_leaves: int = 7,
        learning_rate: float = 0.05,
        random_state: int = 42
    ):
        self.model = LGBMRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            num_leaves=num_leaves,
            learning_rate=learning_rate,
            random_state=random_state,
            objective="regression",
            verbose=-1
        )
        self.feature_names_: list = []
        self.is_fitted_: bool = False

    def fit(self, X: pd.DataFrame, y_true: np.ndarray) -> "LocalLightGBMModel":
        self.feature_names_ = list(X.columns)
        self.model.fit(X, y_true)
        self.is_fitted_ = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted_:
            raise RuntimeError("LocalLightGBMModel is not fitted.")
        return self.model.predict(X[self.feature_names_])

class PhysicalBaselinePredictor:
    """Strategy B0: Mixed air thermal equilibrium estimate."""
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if "MA_TEMP_EST" in X.columns:
            return X["MA_TEMP_EST"].values
        raise ValueError("PhysicalBaselinePredictor requires MA_TEMP_EST feature column.")
