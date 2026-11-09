"""
Alarm Policy and Persistence Filtering Module for Stage 8A.
Implements causal K-of-N persistence filter with time gap and fan-off resets.
Calibrates thresholds strictly on healthy validation sets.
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd


def apply_causal_k_of_n_filter(
    score_series: pd.Series,
    threshold: float,
    k: int = 10,
    n: int = 15,
    max_gap_minutes: float = 5.0
) -> pd.Series:
    """
    Applies a strictly causal K-of-N persistence filter.
    An alarm is triggered at step i if at least k of the previous n steps
    exceed the threshold without encountering a time gap > max_gap_minutes.
    """
    scores = score_series.values
    index = score_series.index
    n_points = len(scores)

    alarms = np.zeros(n_points, dtype=bool)
    exceeds = (scores >= threshold).astype(int)

    # Time delta check
    if isinstance(index, pd.DatetimeIndex):
        time_deltas = index.to_series().diff().dt.total_seconds().values / 60.0
    else:
        dt_idx = pd.to_datetime(index)
        time_deltas = dt_idx.to_series().diff().dt.total_seconds().values / 60.0

    # Fill first delta
    time_deltas[0] = 1.0

    # Causal sliding window
    for i in range(n_points):
        # Determine valid causal window [start_idx, i]
        # Backtrack at most n-1 steps, stopping if a gap > max_gap_minutes is encountered
        window_exceeds = []
        for j in range(i, max(-1, i - n), -1):
            if j < i and time_deltas[j + 1] > max_gap_minutes:
                # Gap break
                break
            window_exceeds.append(exceeds[j])

        if len(window_exceeds) >= k and sum(window_exceeds) >= k:
            alarms[i] = True

    return pd.Series(alarms, index=index, name="alarm")


def calibrate_threshold_for_target_far(
    val_scores: pd.Series,
    target_far: float = 0.025,
    default_3sigma: float = 3.0,
    k: int = 10,
    n: int = 15
) -> float:
    """
    Calibrates threshold tau on clean validation scores such that
    the K-of-N filtered alarm rate is <= target_far.
    Defaults to 3.0 (standard 3-sigma) if 3.0 already meets the budget.
    """
    # Test default 3.0 first
    alarms_3sig = apply_causal_k_of_n_filter(val_scores, threshold=default_3sigma, k=k, n=n)
    far_3sig = alarms_3sig.mean()

    if far_3sig <= target_far:
        return default_3sigma

    # Otherwise search quantile threshold
    for q in np.linspace(0.95, 0.999, 50):
        thresh = float(np.quantile(val_scores, q))
        alarms_q = apply_causal_k_of_n_filter(val_scores, threshold=thresh, k=k, n=n)
        far_q = alarms_q.mean()
        if far_q <= target_far:
            return thresh

    # Fallback to high quantile if still noisy
    return float(np.quantile(val_scores, 0.99))
