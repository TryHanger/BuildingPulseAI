"""
Event-level Evaluation and Scoring Module for Stage 8A.
Scores whole fault episodes without double counting,
evaluates pointwise FAR on normal points, and computes false alarm episodes per 8h day.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def evaluate_events_and_false_alarms(
    alarm_series: pd.Series,
    experiments_df: pd.DataFrame,
    ahu_id: int,
    test_start: str,
    test_end: str,
    method_name: str = "T_ONLY"
) -> Tuple[Dict, pd.DataFrame, List[Dict]]:
    """
    Evaluates detector alarms against ground truth experiments on the test slice.
    """
    # 1. Filter experiments for this AHU within test period
    sub_exp = experiments_df[
        (experiments_df["AHU"] == ahu_id) &
        (experiments_df["Start Datetime"] >= test_start) &
        (experiments_df["End Datetime"] <= test_end)
    ].copy()

    # Sort chronologically
    sub_exp.sort_values("Start Datetime", inplace=True)

    dt_index = pd.to_datetime(alarm_series.index)
    alarm_vals = alarm_series.values

    # 2. Score each experiment
    event_results = []
    # Mask to keep track of fault minutes
    fault_mask = np.zeros(len(dt_index), dtype=bool)

    for idx, row in sub_exp.iterrows():
        e_start = pd.to_datetime(row["Start Datetime"])
        e_end = pd.to_datetime(row["End Datetime"])
        f_type = row["Fault Type"]
        f_mag = row["Magnitude"]

        # Points within [start, end)
        in_event_mask = (dt_index >= e_start) & (dt_index < e_end)
        fault_mask |= in_event_mask

        event_alarms = alarm_vals[in_event_mask]
        n_points = int(in_event_mask.sum())

        detected = bool(np.any(event_alarms)) if n_points > 0 else False
        latency_min = None

        if detected:
            event_indices = np.where(in_event_mask & alarm_vals)[0]
            first_idx = event_indices[0]
            first_time = dt_index[first_idx]
            latency_min = float((first_time - e_start).total_seconds() / 60.0)

        event_results.append({
            "fault_id": int(idx),
            "fault_type": str(f_type),
            "magnitude": float(f_mag) if pd.notnull(f_mag) else None,
            "start": str(e_start),
            "end": str(e_end),
            "duration_minutes": float((e_end - e_start).total_seconds() / 60.0),
            "operating_minutes": n_points,
            "detected": detected,
            "latency_minutes": latency_min
        })

    df_events = pd.DataFrame(event_results)
    total_events = len(df_events)
    detected_events = int(df_events["detected"].sum()) if total_events > 0 else 0
    event_recall = round(detected_events / total_events, 4) if total_events > 0 else 0.0

    # 3. False Alarm Analysis on clean normal operating points
    normal_mask = ~fault_mask
    normal_operating_minutes = int(normal_mask.sum())
    false_alarm_minutes = int((normal_mask & alarm_vals).sum())

    pointwise_far = round(false_alarm_minutes / normal_operating_minutes, 4) if normal_operating_minutes > 0 else 0.0

    # Group contiguous false alarm minutes into episodes
    false_alarm_episodes = []
    in_fa_episode = False
    ep_start = None
    ep_len = 0

    normal_indices = np.where(normal_mask)[0]
    for i in range(len(dt_index)):
        if normal_mask[i] and alarm_vals[i]:
            if not in_fa_episode:
                in_fa_episode = True
                ep_start = dt_index[i]
                ep_len = 1
            else:
                ep_len += 1
        else:
            if in_fa_episode:
                false_alarm_episodes.append({
                    "start": str(ep_start),
                    "duration_minutes": ep_len
                })
                in_fa_episode = False
                ep_start = None
                ep_len = 0

    if in_fa_episode:
        false_alarm_episodes.append({
            "start": str(ep_start),
            "duration_minutes": ep_len
        })

    false_episodes_count = len(false_alarm_episodes)
    operating_8h_days = normal_operating_minutes / 480.0
    false_episodes_per_8h_day = round(false_episodes_count / operating_8h_days, 4) if operating_8h_days > 0 else 0.0

    # Per-family recall
    family_recall = {}
    if total_events > 0:
        for ftype, grp in df_events.groupby("fault_type"):
            family_recall[ftype] = {
                "total": len(grp),
                "detected": int(grp["detected"].sum()),
                "recall": round(float(grp["detected"].sum()) / len(grp), 4)
            }

    summary = {
        "method": method_name,
        "ahu_id": ahu_id,
        "total_fault_events": total_events,
        "detected_fault_events": detected_events,
        "event_recall": event_recall,
        "normal_operating_minutes": normal_operating_minutes,
        "false_alarm_minutes": false_alarm_minutes,
        "pointwise_far": pointwise_far,
        "false_alarm_episodes_count": false_episodes_count,
        "false_episodes_per_8h_day": false_episodes_per_8h_day,
        "family_recall": family_recall
    }

    return summary, df_events, false_alarm_episodes
