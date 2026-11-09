"""
Evaluation metrics for domain adaptation and fault detection on CSIRO AHU9.
Computes:
  - Regression metrics: MAE, RMSE, Mean Bias, R2.
  - Alarm metrics: False Alarm Rate, False Alarm Episodes/Day, Median Alarm Duration.
  - FDD Event metrics: Event Recall per fault episode, detection delay.
Guarantees clean handling of zero division / empty sets.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> Dict[str, Optional[float]]:
    """Calculates standard regression error metrics."""
    if len(y_true) == 0 or len(y_pred) == 0:
        return {
            "count": 0,
            "mae_degC": None,
            "rmse_degC": None,
            "mean_bias_degC": None,
            "r2": None
        }

    residuals = y_true - y_pred
    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals**2)))
    mean_bias = float(np.mean(residuals))

    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-9 else None

    return {
        "count": int(len(y_true)),
        "mae_degC": round(mae, 4),
        "rmse_degC": round(rmse, 4),
        "mean_bias_degC": round(mean_bias, 4),
        "r2": round(r2, 4) if r2 is not None else None
    }

def apply_persistence_filter(
    breaches: np.ndarray,
    k: int = 10,
    n: int = 15
) -> np.ndarray:
    """
    Applies causal sliding-window persistence filter:
    Alarm triggers if at least k of the past n samples exceeded threshold.
    """
    if len(breaches) == 0:
        return np.array([], dtype=bool)

    s = pd.Series(breaches.astype(int))
    rolling_sum = s.rolling(window=n, min_periods=1).sum().values
    return rolling_sum >= k

def compute_alarm_episodes(alarms: np.ndarray) -> List[int]:
    """Calculates lengths of contiguous alarm episodes."""
    if len(alarms) == 0:
        return []

    episodes = []
    current_len = 0
    for a in alarms:
        if a:
            current_len += 1
        else:
            if current_len > 0:
                episodes.append(current_len)
                current_len = 0
    if current_len > 0:
        episodes.append(current_len)
    return episodes

def compute_fdd_metrics(
    residuals: np.ndarray,
    threshold: float,
    is_fault: np.ndarray,
    fault_episodes_meta: List[Dict[str, Any]],
    k_persistence: int = 10,
    n_window: int = 15,
    minutes_per_workday: int = 480
) -> Dict[str, Any]:
    """
    Computes rigorous FDD alarm and recall metrics.
    Separates healthy points (false alarm calculation) from fault points (recall).
    """
    breaches = np.abs(residuals) >= threshold
    alarms = apply_persistence_filter(breaches, k=k_persistence, n=n_window)

    normal_mask = ~is_fault
    normal_minutes = int(normal_mask.sum())
    normal_alarms = alarms[normal_mask]

    false_alarm_minutes = int(normal_alarms.sum())
    false_alarm_rate = float(false_alarm_minutes / normal_minutes) if normal_minutes > 0 else None

    episodes = compute_alarm_episodes(normal_alarms)
    episode_count = len(episodes)
    episodes_per_day = float((episode_count / normal_minutes) * minutes_per_workday) if normal_minutes > 0 else None
    median_duration = float(np.median(episodes)) if episodes else None

    # Event recall across provided fault episodes
    detected_episodes = 0
    total_episodes = len(fault_episodes_meta)

    episode_details = []
    for ep in fault_episodes_meta:
        # Check if episode has at least one active alarm
        ep_indices = ep.get("test_indices", [])
        if len(ep_indices) == 0:
            continue
        ep_alarms = alarms[ep_indices]
        is_detected = bool(ep_alarms.any())
        first_det_delay = None
        if is_detected:
            detected_episodes += 1
            first_idx = int(np.where(ep_alarms)[0][0])
            first_det_delay = first_idx

        episode_details.append({
            "fault_type": ep.get("fault_type", "Unknown"),
            "severity": ep.get("severity", "N/A"),
            "start": str(ep.get("start")),
            "end": str(ep.get("end")),
            "duration_points": len(ep_indices),
            "detected": is_detected,
            "delay_minutes": first_det_delay
        })

    event_recall = float(detected_episodes / total_episodes) if total_episodes > 0 else None

    return {
        "threshold": round(threshold, 4),
        "persistence_k_of_n": f"{k_persistence}/{n_window}",
        "normal_points_count": normal_minutes,
        "false_alarm_minutes": false_alarm_minutes,
        "false_alarm_rate": round(false_alarm_rate, 4) if false_alarm_rate is not None else None,
        "false_alarm_episodes_count": episode_count,
        "false_alarm_episodes_per_normal_day": round(episodes_per_day, 4) if episodes_per_day is not None else None,
        "median_alarm_duration_minutes": round(median_duration, 1) if median_duration is not None else None,
        "total_fault_episodes": total_episodes,
        "detected_fault_episodes": detected_episodes,
        "event_recall": round(event_recall, 4) if event_recall is not None else None,
        "episode_details": episode_details
    }
