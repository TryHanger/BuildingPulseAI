"""
Residual Computation and Fusion Module for Stage 8A.
Computes signed, absolute, and normalized residuals for temperature (T) and control (U),
as well as pre-registered fusion scores.
"""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


def compute_normalized_residuals(
    y_true_T: np.ndarray,
    y_pred_T: np.ndarray,
    sigma_T_val: float,
    y_true_u: np.ndarray,
    y_pred_u: np.ndarray,
    sigma_u_val: float,
    index: pd.Index
) -> pd.DataFrame:
    """
    Computes absolute and standardized residuals, plus fused scores.
    """
    # 1. Temperature residuals
    res_T_signed = y_true_T - y_pred_T
    res_T_abs = np.abs(res_T_signed)
    z_T = res_T_abs / max(sigma_T_val, 1e-4)

    # 2. Control residuals
    res_u_signed = y_true_u - y_pred_u
    res_u_abs = np.abs(res_u_signed)
    z_u = res_u_abs / max(sigma_u_val, 1e-4)

    # 3. Fusion scores
    s_max = np.maximum(z_T, z_u)
    s_l2 = np.sqrt(0.5 * (z_T**2 + z_u**2))

    df_residuals = pd.DataFrame(index=index)
    df_residuals["y_true_T"] = y_true_T
    df_residuals["y_pred_T"] = y_pred_T
    df_residuals["r_T"] = res_T_abs
    df_residuals["z_T"] = z_T

    df_residuals["y_true_u"] = y_true_u
    df_residuals["y_pred_u"] = y_pred_u
    df_residuals["r_u"] = res_u_abs
    df_residuals["z_u"] = z_u

    df_residuals["s_max"] = s_max
    df_residuals["s_l2"] = s_l2

    return df_residuals
