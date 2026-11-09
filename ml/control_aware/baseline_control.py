"""
Baseline Control Effort Model for Stage 8A.
Estimates the expected normal actuator command u_hat based on exogenous context.
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class ControlEffortModel:
    """
    Model predicting expected control effort u_hat (e.g. cooling valve command CHWC_VLV_DM)
    under normal operating conditions.
    """

    def __init__(self, model_type: str = "ridge", alpha: float = 1.0, random_state: int = 42):
        self.model_type = model_type
        self.alpha = alpha
        self.random_state = random_state
        self.feature_names = []
        self.is_fitted = False
        self.val_residual_std = 1.0
        self.val_mae = 0.0
        self.val_r2 = 0.0

        if model_type == "ridge":
            self.model = Ridge(alpha=alpha, random_state=random_state)
        elif model_type == "hist_gbm":
            self.model = HistGradientBoostingRegressor(
                max_depth=3,
                max_iter=50,
                learning_rate=0.05,
                random_state=random_state
            )
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series) -> "ControlEffortModel":
        self.feature_names = list(X_train.columns)
        self.model.fit(X_train.values, y_train.values)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model is not fitted yet!")
        preds = self.model.predict(X[self.feature_names].values)
        # Actuator command is bounded in [0.0, 1.0]
        return np.clip(preds, 0.0, 1.0)

    def calibrate_on_validation(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ) -> Dict[str, float]:
        """
        Calibrates healthy validation residual scale and returns validation metrics.
        """
        preds = self.predict(X_val)
        residuals = y_val.values - preds
        self.val_mae = float(mean_absolute_error(y_val.values, preds))
        self.val_r2 = float(r2_score(y_val.values, preds))
        self.val_residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 1.0
        if self.val_residual_std < 1e-4:
            self.val_residual_std = 1e-4

        return {
            "val_mae": self.val_mae,
            "val_r2": self.val_r2,
            "val_residual_std": self.val_residual_std,
            "val_points_count": len(y_val)
        }
