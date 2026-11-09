"""
BuildingPulse AI — Time-Aware Causal Scoring and DomainGuard Engine
Stage 8B-R.2 Implementation.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


class CalibratedDomainGuard:
    """
    Evaluates whether an input sample lies within the valid operational domain.
    Supports:
    - Strict Train Min-Max
    - Calibrated Dev Envelope (Train + Val)
    - Statistical Margin / Mahalanobis-like Z-envelope
    """
    def __init__(self, df_train: pd.DataFrame, df_val: Optional[Any] = None, features: Optional[List[str]] = None):
        if isinstance(df_val, list) and features is None:
            features = df_val
            df_val = df_train
        elif df_val is None:
            df_val = df_train
        self.features = features
        self.train_bounds = {
            f: (float(df_train[f].min()), float(df_train[f].max())) for f in features
        }
        df_dev = pd.concat([df_train, df_val])
        self.dev_bounds = {
            f: (float(df_dev[f].min()), float(df_dev[f].max())) for f in features
        }
        # Statistical envelope: mean +/- 3.5 std on Dev
        self.stat_bounds = {}
        for f in features:
            mu = float(df_dev[f].mean())
            s = float(df_dev[f].std(ddof=1)) if len(df_dev) > 1 else 1.0
            self.stat_bounds[f] = (mu - 3.5 * s, mu + 3.5 * s)
            
    def check_point(self, sample: Dict[str, float], mode: str = "dev_envelope") -> Dict[str, Any]:
        """
        Evaluates an individual feature vector against calibrated boundaries.
        Explicitly guards against non-finite values (NaN, +Inf, -Inf), missing keys,
        and invalid data types, returning 'INVALID_INPUT' (OOD/abstention) rather than 'IN_DOMAIN'.
        """
        if mode == "strict_train":
            bounds = self.train_bounds
        elif mode == "dev_envelope":
            bounds = self.dev_bounds
        elif mode == "statistical":
            bounds = self.stat_bounds
        else:
            raise ValueError(f"Unknown guard mode: {mode}")
            
        ood_features = []
        invalid_features = []
        for f in self.features:
            if f not in sample:
                invalid_features.append(f)
                continue
            try:
                val = float(sample[f])
            except (ValueError, TypeError):
                invalid_features.append(f)
                continue
                
            if not np.isfinite(val):
                invalid_features.append(f)
                continue
                
            low, high = bounds[f]
            if val < low or val > high:
                ood_features.append(f)
                
        is_invalid = len(invalid_features) > 0
        is_ood = len(ood_features) > 0 or is_invalid
        
        if is_invalid:
            status = "INVALID_INPUT"
        elif is_ood:
            status = "OOD"
        else:
            status = "IN_DOMAIN"
            
        return {
            "is_ood": is_ood,
            "is_invalid": is_invalid,
            "ood_count": len(ood_features) + len(invalid_features),
            "ood_features": ood_features + invalid_features,
            "invalid_features": invalid_features,
            "domain_status": status
        }


def apply_time_aware_causal_k_of_n(
    timestamps,
    z_scores: np.ndarray,
    threshold: float,
    k: int = 2,
    n: int = 3,
    active_mask: Optional[np.ndarray] = None,
    max_gap_minutes: float = 15.0
) -> np.ndarray:
    """
    Causal K-of-N persistence filter with physical gap awareness:
    - Resets history if time elapsed between consecutive samples >= max_gap_minutes (e.g. >= 15 min).
    - Preserves history across single packet drops (e.g. 10 min <= max_gap_minutes) to absorb BACnet jitter.
    - Resets history if active_mask is False (e.g. fan off or abstained).
    """
    n_pts = len(z_scores)
    alarms = np.zeros(n_pts, dtype=bool)
    
    if active_mask is None:
        active_mask = np.ones(n_pts, dtype=bool)
        
    ts = pd.to_datetime(timestamps).values
    history = []
    
    for i in range(n_pts):
        if not active_mask[i]:
            # Reset history when inactive
            history = []
            alarms[i] = False
            continue
            
        # Check gap with previous point in history
        if i > 0:
            diff_ns = ts[i] - ts[i - 1]
            if pd.isna(diff_ns) or str(diff_ns) == 'NaT':
                history = []
            else:
                dt_min = float(diff_ns.astype('timedelta64[s]').astype(float) / 60.0)
                if np.isnan(dt_min) or dt_min >= max_gap_minutes:
                    # Reset history on physical telemetry gap (>= 15 min)
                    history = []
                
        exceeded = int(z_scores[i] >= threshold)
        history.append(exceeded)
        if len(history) > n:
            history.pop(0)
            
        if len(history) >= k and sum(history) >= k and exceeded == 1:
            alarms[i] = True
        else:
            alarms[i] = False
            
    return alarms


def count_calendar_time_episodes(
    timestamps,
    binary_alarms: np.ndarray,
    valid_mask: np.ndarray,
    max_gap_minutes: float = 15.0
) -> int:
    """
    Counts false alarm episodes on the full continuous calendar grid.
    An episode is a continuous run of True alarms.
    The episode terminates whenever:
    1. binary_alarms becomes False.
    2. valid_mask becomes False (fan turns off, or OOD abstention).
    3. A time gap >= max_gap_minutes occurs (>= 15 min).
    """
    n = len(binary_alarms)
    episode_count = 0
    in_episode = False
    ts = pd.to_datetime(timestamps).values
    
    for i in range(n):
        if i > 0:
            diff_ns = ts[i] - ts[i - 1]
            if pd.isna(diff_ns) or str(diff_ns) == 'NaT':
                in_episode = False
            else:
                dt_min = float(diff_ns.astype('timedelta64[s]').astype(float) / 60.0)
                if np.isnan(dt_min) or dt_min >= max_gap_minutes:
                    in_episode = False
                
        is_active_alarm = bool(binary_alarms[i] and valid_mask[i])
        
        if is_active_alarm:
            if not in_episode:
                in_episode = True
                episode_count += 1
        else:
            in_episode = False
            
    return episode_count
