from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from ml.virtual_sensor.schemas import ThresholdConfig, PersistenceFilterConfig

def compute_residuals(y_true: pd.Series, y_pred: np.ndarray) -> Tuple[pd.Series, pd.Series]:
    """Computes signed and absolute residuals: r = y_true - y_pred, |r| = abs(r)."""
    signed = y_true - y_pred
    abs_res = signed.abs()
    return signed, abs_res

def calibrate_thresholds(abs_residuals_val: pd.Series, operating_mask: pd.Series) -> ThresholdConfig:
    """
    Calibrates residual detection thresholds strictly on validation operating points.
    Does NOT use any fault data or ground truth labels.
    """
    valid_res = abs_residuals_val[operating_mask].dropna()
    if len(valid_res) == 0:
        return ThresholdConfig(q95=1.0, q99=2.0, three_sigma=2.5, mad=1.5)

    q95 = float(np.percentile(valid_res, 95))
    q99 = float(np.percentile(valid_res, 99))

    mean_val = float(valid_res.mean())
    std_val = float(valid_res.std())
    three_sigma = float(mean_val + 3.0 * std_val)

    med = float(valid_res.median())
    mad_val = float(np.median(np.abs(valid_res - med)))
    mad_threshold = float(med + 3.0 * 1.4826 * mad_val)

    return ThresholdConfig(
        q95=round(q95, 3),
        q99=round(q99, 3),
        three_sigma=round(three_sigma, 3),
        mad=round(mad_threshold, 3)
    )

def apply_persistence_filter(
    abs_residuals: pd.Series,
    threshold: float,
    operating_mask: pd.Series,
    config: PersistenceFilterConfig
) -> pd.Series:
    """
    Causal rolling persistence alarm filter.
    Triggered when >= K points out of the last N operating points exceed threshold.
    Strictly causal (no future data leakage).
    """
    raw_over = (abs_residuals > threshold) & operating_mask
    # Rolling sum of booleans over window N
    rolling_hits = raw_over.astype(int).rolling(window=config.n, min_periods=1).sum()
    alarm_mask = (rolling_hits >= config.k) & operating_mask
    return alarm_mask

def count_alarm_episodes(alarm_mask: pd.Series) -> int:
    """Counts discrete contiguous episodes of alarm."""
    diff = (alarm_mask.astype(int).diff() == 1)
    if alarm_mask.iloc[0] if len(alarm_mask) > 0 else False:
        return int(diff.sum()) + 1
    return int(diff.sum())
