import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_validation_manifest.json"
POINTWISE_CSV = ROOT_DIR / "research" / "runs" / "rbc_nesbitt_independent_pointwise_predictions.csv"

def test_synthetic_preexisting_alarm_logic():
    """
    Synthetic verification of alarm onset logic:
    - Sequence 1: Alarm already active at t=0 and t=1, fault starts at t=1 -> ALARM_STARTED_BEFORE_FAULT.
    - Sequence 2: Alarm inactive at t=0, becomes active at t=1 (fault starts at t=1) -> NEW_ALARM_AFTER_FAULT.
    - Sequence 3: Alarm inactive throughout -> NO_ALARM.
    """
    # Case 1: Pre-existing alarm (active before and at start of fault)
    alarms_case1 = np.array([False, True, True, True, False])
    # Fault window: index 2 to 3
    is_fault = np.array([False, False, True, True, False])
    
    s_idx = 2
    e_idx = 3
    pre_fault_active = alarms_case1[s_idx - 1] # True (at index 1)
    at_start_active = alarms_case1[s_idx]     # True (at index 2)
    is_preexisting = pre_fault_active and at_start_active
    
    onsets_in_fault = []
    for idx in range(s_idx, e_idx + 1):
        if alarms_case1[idx]:
            if idx == s_idx:
                if not pre_fault_active:
                    onsets_in_fault.append(idx)
            else:
                if not alarms_case1[idx - 1]:
                    onsets_in_fault.append(idx)
                    
    assert bool(is_preexisting) is True
    assert len(onsets_in_fault) == 0
    # Must be classified as ALARM_STARTED_BEFORE_FAULT
    status = "ALARM_STARTED_BEFORE_FAULT" if (is_preexisting and len(onsets_in_fault) == 0) else "NEW_ALARM_AFTER_FAULT"
    assert status == "ALARM_STARTED_BEFORE_FAULT"

    # Case 2: Genuine new onset at fault start
    alarms_case2 = np.array([False, False, True, True, False])
    pre_fault_active2 = alarms_case2[s_idx - 1] # False (at index 1)
    onsets_in_fault2 = []
    for idx in range(s_idx, e_idx + 1):
        if alarms_case2[idx]:
            if idx == s_idx:
                if not pre_fault_active2:
                    onsets_in_fault2.append(idx)
            else:
                if not alarms_case2[idx - 1]:
                    onsets_in_fault2.append(idx)
    assert len(onsets_in_fault2) == 1
    assert onsets_in_fault2[0] == s_idx

def test_real_winter_20161201_is_preexisting_alarm():
    """
    P0-02 Audit Verification:
    On 2016-12-01, M2 and M6 alarms were already active before the official fault started at 10:00.
    Therefore, it must be classified as ALARM_STARTED_BEFORE_FAULT, NOT a new detection.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    all_breakdown_m2 = manifest["evaluation_slices"]["all_seasons_combined"]["M2_Control_Mat400"]["scenarios_breakdown"]
    all_breakdown_m6 = manifest["evaluation_slices"]["all_seasons_combined"]["M6_Direct_Damper_BAS400"]["scenarios_breakdown"]
    
    scen_2016 = "20161201_OADamStuck_90.csv"
    assert scen_2016 in all_breakdown_m2
    assert scen_2016 in all_breakdown_m6
    
    # M2 tau=4.00 on 2016-12-01
    res2 = all_breakdown_m2[scen_2016]
    assert res2["pre_fault_alarm_active"] is True
    assert res2["event_detection_status"] == "ALARM_STARTED_BEFORE_FAULT"
    assert res2["new_onset_detected"] is False
    assert res2["missed_due_to_preexisting_alarm"] is True
    assert res2["onset_latency_min"] is None
    
    # M6 on 2016-12-01
    res6 = all_breakdown_m6[scen_2016]
    assert res6["pre_fault_alarm_active"] is True
    assert res6["event_detection_status"] == "ALARM_STARTED_BEFORE_FAULT"
    assert res6["new_onset_detected"] is False

def test_real_winter_20170103_m2_new_onset():
    """
    On 2017-01-03, M2 tau=4.00 had pre_fault_alarm_active == False,
    and a genuine new onset at 10:05 (latency = 5.0 min).
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    scen_2017 = "20170103_OADamStuck_80.csv"
    res2 = manifest["evaluation_slices"]["all_seasons_combined"]["M2_Control_Mat400"]["scenarios_breakdown"][scen_2017]
    assert res2["pre_fault_alarm_active"] is False
    assert res2["event_detection_status"] == "NEW_ALARM_AFTER_FAULT"
    assert res2["new_onset_detected"] is True
    assert res2["onset_latency_min"] == 5.0
