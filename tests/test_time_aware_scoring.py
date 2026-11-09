"""
Unit Tests for Time-Aware Scoring & Gap Breaking
Demonstrates resolution of finding P1-E (Gate 4).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from ml.diagnostics.time_aware_fdd import (
    apply_time_aware_causal_k_of_n,
    count_calendar_time_episodes
)


def test_gap_and_fan_off_breaks_false_alarm_episodes():
    """
    P1-E: Prove that when a fan turns off or a gap occurs between alarms,
    they are counted as TWO distinct episodes, rather than being merged.
    """
    # 6 points spaced by 5 minutes:
    # 10:00 (alarm), 10:05 (alarm), 10:10 (fan off / inactive), 10:15 (fan off), 10:20 (fan on, alarm), 10:25 (alarm)
    times = pd.to_datetime([
        "2017-07-18 10:00:00",
        "2017-07-18 10:05:00",
        "2017-07-18 10:10:00",
        "2017-07-18 10:15:00",
        "2017-07-18 10:20:00",
        "2017-07-18 10:25:00"
    ])
    raw_alarms = np.array([True, True, True, True, True, True])
    valid_mask = np.array([True, True, False, False, True, True]) # fan off at 10:10 and 10:15
    
    # Old flawed logic (compressing mask first):
    compressed_alarms = raw_alarms[valid_mask] # [True, True, True, True] -> contiguous run = 1 episode!
    naive_episode_count = 0
    in_ep = False
    for a in compressed_alarms:
        if a:
            if not in_ep:
                in_ep = True
                naive_episode_count += 1
        else:
            in_ep = False
    assert naive_episode_count == 1, "Naive compressed logic erroneously merges across fan-off gap!"
    
    # New time-aware logic:
    time_aware_ep_count = count_calendar_time_episodes(times, raw_alarms, valid_mask, max_gap_minutes=15.0)
    assert time_aware_ep_count == 2, f"Time-aware scoring must count 2 episodes, got {time_aware_ep_count}!"


def test_telemetry_gap_breaks_episodes():
    """Prove that a 2-hour telemetry gap breaks an ongoing alarm into two episodes."""
    times = pd.to_datetime([
        "2017-07-18 08:00:00",
        "2017-07-18 08:05:00",
        # 2-hour gap
        "2017-07-18 10:05:00",
        "2017-07-18 10:10:00"
    ])
    alarms = np.array([True, True, True, True])
    mask = np.array([True, True, True, True])
    
    ep_count = count_calendar_time_episodes(times, alarms, mask, max_gap_minutes=15.0)
    assert ep_count == 2, f"Expected 2 episodes across 2-hour gap, got {ep_count}"


def test_k_of_n_resets_on_gap():
    """Verify that K-of-N persistence filter does NOT accumulate across physical gaps."""
    times = pd.to_datetime([
        "2017-07-18 08:00:00", # exceed (count=1)
        # 1-hour gap
        "2017-07-18 09:00:00", # exceed (after gap: should start fresh count=1, NOT trigger 2-of-3!)
        "2017-07-18 09:05:00"  # exceed (count=2: NOW trigger 2-of-3)
    ])
    z = np.array([4.0, 4.0, 4.0])
    
    alarms = apply_time_aware_causal_k_of_n(times, z, threshold=3.5, k=2, n=3, max_gap_minutes=15.0)
    
    # At 08:00: 1st exceed -> False
    assert alarms[0] == False
    # At 09:00: 1st after gap -> False (must NOT trigger with 08:00 point)
    assert alarms[1] == False
    # At 09:05: 2nd consecutive -> True
    assert alarms[2] == True
