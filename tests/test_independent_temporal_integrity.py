"""Independent tests for Stage 8B-R.3 temporal integrity and strict JSON.
Verifies that real BMS timestamps are never NaT, gap-breaks reset K-of-N memory,
and manifest serializes strictly without nonstandard NaN values.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, RAW_DIR
from ml.diagnostics.time_aware_fdd import (
    apply_time_aware_causal_k_of_n,
    count_calendar_time_episodes,
)


def test_real_csv_loader_timestamp_integrity():
    file = RAW_DIR / "20170718_OADamStuck_100.csv"
    frame = load_clean_nesbitt(file)
    assert frame['timestamp'].notna().all(), 'Real BMS timestamps must never be NaT'
    assert frame['timestamp'].is_monotonic_increasing
    assert np.array_equal(frame['timestamp'].values, frame.index.values)
    assert (frame['timestamp'].diff().dropna() == pd.Timedelta(minutes=5)).all()


def test_real_loader_gap_reset():
    frame = load_clean_nesbitt(RAW_DIR / "20170718_OADamStuck_100.csv")
    sample = frame.iloc[[0, 1, 40]]
    scores = np.array([10.0, 0.0, 10.0])
    alarm = apply_time_aware_causal_k_of_n(
        timestamps=sample['timestamp'], z_scores=scores, threshold=5.0, k=2, n=3,
        max_gap_minutes=15.0,
    )
    assert alarm.tolist() == [False, False, False], 'Must reset memory across >15 min gap'


def test_real_loader_false_episode_gap_break():
    frame = load_clean_nesbitt(RAW_DIR / '20170718_OADamStuck_100.csv')
    sample = frame.iloc[[0, 40]]
    result = count_calendar_time_episodes(
        timestamps=sample['timestamp'], binary_alarms=np.array([True, True]),
        valid_mask=np.array([True, True]), max_gap_minutes=15.0,
    )
    assert result == 2, 'Two isolated alarms must not merge across a 200-minute gap'


def test_machine_manifest_strict_json_and_finite_latencies():
    p = Path('research/runs/rbc_nesbitt_reconciled_manifest.json')
    def reject_constant(x):
        raise ValueError(f'Nonstandard numeric constant in JSON: {x}')
    obj = json.loads(p.read_text(encoding='utf-8'), parse_constant=reject_constant)
    res = obj['reconciled_evaluation_matrix']['M2_U_ONLY_TAU_3_5']['official_all_4']
    for scenario in res['scenarios_breakdown'].values():
        delay = scenario['latency_minutes']
        if scenario['episode_detected']:
            assert delay is not None and np.isfinite(delay), 'Detected event must have valid latency'
