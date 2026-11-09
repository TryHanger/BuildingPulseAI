import pytest
import numpy as np
import pandas as pd
from ml.diagnostics.time_aware_fdd import CalibratedDomainGuard, apply_time_aware_causal_k_of_n, count_calendar_time_episodes

def test_domain_guard_nan_and_invalid_inputs():
    df_train = pd.DataFrame({
        "feat1": [10.0, 20.0, 30.0],
        "feat2": [100.0, 200.0, 300.0]
    })
    guard = CalibratedDomainGuard(df_train, df_train, features=["feat1", "feat2"])

    # 1. Normal valid input
    res_valid = guard.check_point({"feat1": 15.0, "feat2": 250.0})
    assert res_valid["is_ood"] is False
    assert res_valid["is_invalid"] is False
    assert res_valid["domain_status"] == "IN_DOMAIN"

    # 2. NaN value input
    res_nan = guard.check_point({"feat1": np.nan, "feat2": 200.0})
    assert res_nan["is_ood"] is True
    assert res_nan["is_invalid"] is True
    assert res_nan["domain_status"] == "INVALID_INPUT"
    assert "feat1" in res_nan["invalid_features"]

    # 3. +Inf and -Inf
    res_inf = guard.check_point({"feat1": float("inf"), "feat2": 200.0})
    assert res_inf["is_ood"] is True
    assert res_inf["is_invalid"] is True
    assert res_inf["domain_status"] == "INVALID_INPUT"
    assert "feat1" in res_inf["invalid_features"]

    res_neginf = guard.check_point({"feat1": 15.0, "feat2": float("-inf")})
    assert res_neginf["is_ood"] is True
    assert res_neginf["is_invalid"] is True
    assert res_neginf["domain_status"] == "INVALID_INPUT"
    assert "feat2" in res_neginf["invalid_features"]

    # 4. Missing key
    res_missing = guard.check_point({"feat1": 15.0})
    assert res_missing["is_ood"] is True
    assert res_missing["is_invalid"] is True
    assert res_missing["domain_status"] == "INVALID_INPUT"
    assert "feat2" in res_missing["invalid_features"]

    # 5. Invalid string / unparseable
    res_bad = guard.check_point({"feat1": "corrupt_sensor", "feat2": 200.0})
    assert res_bad["is_ood"] is True
    assert res_bad["is_invalid"] is True
    assert res_bad["domain_status"] == "INVALID_INPUT"
    assert "feat1" in res_bad["invalid_features"]


def test_gap_policy_5_10_15_20_minutes_k_of_n():
    """
    K-of-N persistence filter gap policy:
    - Normal BACnet intervals: 5 min
    - Minor network jitter: 10 min (dt < 15 min -> preserved)
    - Major physical telemetry gap: 15 min and 20 min (dt >= 15 min -> history reset)
    """
    # Case 1: 5-minute interval (normal)
    # Point 0: residual high
    # Point 1 (t+5m): residual high -> alarm should fire (2 of 3)
    t0 = pd.Timestamp("2026-01-01 12:00:00")
    ts_5m = [t0, t0 + pd.Timedelta(minutes=5)]
    z = np.array([4.0, 4.0])
    res_5m = apply_time_aware_causal_k_of_n(ts_5m, z, threshold=3.0, k=2, n=3, max_gap_minutes=15.0)
    assert res_5m[0] is False or res_5m[0] == False
    assert res_5m[1] == True, "5 min interval should satisfy 2-of-3 persistence"

    # Case 2: 10-minute interval (single drop, dt=10m < 15m)
    # History preserved across single packet drop
    ts_10m = [t0, t0 + pd.Timedelta(minutes=10)]
    res_10m = apply_time_aware_causal_k_of_n(ts_10m, z, threshold=3.0, k=2, n=3, max_gap_minutes=15.0)
    assert res_10m[1] == True, "10 min gap (<15m) should preserve memory and fire alarm"

    # Case 3: 15-minute interval (dt=15m >= 15m)
    # History MUST be reset -> Point 1 is treated as first point in new sequence (len(history)=1 < k=2)
    ts_15m = [t0, t0 + pd.Timedelta(minutes=15)]
    res_15m = apply_time_aware_causal_k_of_n(ts_15m, z, threshold=3.0, k=2, n=3, max_gap_minutes=15.0)
    assert res_15m[1] == False, "15 min gap (>=15m) must reset memory, so alarm cannot fire on 1st point after gap"

    # Case 4: 20-minute interval (dt=20m >= 15m)
    # History MUST be reset -> Point 1 cannot fire alarm
    ts_20m = [t0, t0 + pd.Timedelta(minutes=20)]
    res_20m = apply_time_aware_causal_k_of_n(ts_20m, z, threshold=3.0, k=2, n=3, max_gap_minutes=15.0)
    assert res_20m[1] == False, "20 min gap (>=15m) must reset memory"


def test_gap_policy_5_10_15_20_minutes_episodes():
    """
    Calendar time episodes counting:
    - 5m and 10m gaps between continuous active alarms remain within same episode (dt < 15 min).
    - 15m and 20m gaps break the episode, so continuing alarm after gap counts as a second episode.
    """
    t0 = pd.Timestamp("2026-01-01 12:00:00")

    # 10m gap between two alarms: dt=10 < 15 -> Single episode of length 2
    ts_10m = [t0, t0 + pd.Timedelta(minutes=10)]
    alarms = np.array([True, True])
    valid = np.array([True, True])
    episodes_10m = count_calendar_time_episodes(ts_10m, alarms, valid, max_gap_minutes=15.0)
    assert episodes_10m == 1, "10 min gap (<15m) should not break active episode"

    # 15m gap between two alarms: dt=15 >= 15 -> Episode broken, resulting in 2 episodes
    ts_15m = [t0, t0 + pd.Timedelta(minutes=15)]
    episodes_15m = count_calendar_time_episodes(ts_15m, alarms, valid, max_gap_minutes=15.0)
    assert episodes_15m == 2, "15 min gap (>=15m) must terminate episode and start a new one"

    # 20m gap between two alarms: dt=20 >= 15 -> Episode broken, resulting in 2 episodes
    ts_20m = [t0, t0 + pd.Timedelta(minutes=20)]
    episodes_20m = count_calendar_time_episodes(ts_20m, alarms, valid, max_gap_minutes=15.0)
    assert episodes_20m == 2, "20 min gap (>=15m) must terminate episode and start a new one"
