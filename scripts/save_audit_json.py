import sys
sys.path.insert(0, ".")
import json
from datetime import datetime, timezone

audit_data = {
    "audit_metadata": {
        "gate": "Gate 8B.0",
        "description": "Scientific, dataset, and metric audit of Stage 8A prior to Stage 8B dynamic modeling",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED_CONDITIONAL_GO"
    },
    "finding_1_event_transition_34_to_36": {
        "ahu_id": 9,
        "stage6_denominator": 34,
        "stage8a_denominator": 36,
        "new_event_ids": [254, 255],
        "details": {
            "event_254": {
                "fault_type": "Zone Average Temp Drift",
                "magnitude": -2.0,
                "start": "2013-11-07 08:30:31",
                "end": "2013-11-07 09:30:53",
                "operating_minutes": 31,
                "fan_off_minutes": 29,
                "stage6_excluded_reason": "Filter 'start >= 2013-11-07 09:00:00' excluded events starting before 09:00.",
                "stage8a_included_reason": "Filter 'start >= 2013-11-07 00:00:00' included full calendar day.",
                "detected_by_t_only": False,
                "detected_by_u_only": False,
                "detected_by_fusion": False
            },
            "event_255": {
                "fault_type": "OA Damper Stuck Open",
                "magnitude": 64.0,
                "start": "2013-11-07 08:30:42",
                "end": "2013-11-07 09:30:56",
                "operating_minutes": 31,
                "fan_off_minutes": 29,
                "stage6_excluded_reason": "Filter 'start >= 2013-11-07 09:00:00' excluded events starting before 09:00.",
                "stage8a_included_reason": "Filter 'start >= 2013-11-07 00:00:00' included full calendar day.",
                "detected_by_t_only": False,
                "detected_by_u_only": False,
                "detected_by_fusion": False
            }
        },
        "conclusion": "The numerator of detected events for T_ONLY is identically 6. Recall changed from 6/34 (17.65%) to 6/36 (16.67%) purely due to expanding the test window start from 09:00 to 00:00."
    },
    "finding_2_train_val_cleanliness_discrepancy": {
        "documentation_error_in_stage8a": "docs/STAGE8A_AHU9_AHU10_INVENTORY.md line 76 claimed 0 fault experiments between 2013-10-28 and 2013-11-06.",
        "actual_ground_truth": {
            "ahu9_train_experiments": 9,
            "ahu9_val_experiments": 9,
            "ahu10_train_experiments": 12,
            "ahu10_val_experiments": 9
        },
        "implementation_difference": {
            "ahu9": "evaluate_stage8a.py used CSIROTemporalSplitter(embargo_minutes=60), which correctly removed all 18 fault windows plus 60-min embargo margins, leaving clean operating points (Train: 1588, Val: 726).",
            "ahu10": "CRITICAL CODE DEFECT IN STAGE 8A: evaluate_stage8a.py used get_stage8a_split(df10, filter_operating=True) which DID NOT apply CSIROTemporalSplitter or any fault masking. AHU10 was fitted and calibrated on data containing 21 active fault injection experiments."
        }
    },
    "finding_3_calendar_and_sampling_audit": {
        "ahu9": {
            "total_rows": 457653,
            "nulls": 0,
            "duplicates": 0,
            "step_30s_pct": 98.55,
            "gaps_gt_60s_count": 6610,
            "non_monotonic_count": 0
        },
        "ahu10": {
            "total_rows": 422169,
            "nulls": 0,
            "duplicates": 0,
            "step_30s_pct": 98.43,
            "gaps_gt_60s_count": 6592,
            "non_monotonic_count": 0
        },
        "operational_cycle": "Daily operating regime runs 09:00 to 17:00 (8h). Every day ends with a 16-hour (960 min) overnight shutdown gap. A 10-minute sensor dropout occurs on 2013-11-05 11:39:01 to 11:49:01.",
        "dynamic_requirement": "State/lag variables and filters MUST reset whenever delta_t > 120s or fan toggles from OFF to ON, to prevent state contamination across overnight shutdowns."
    },
    "finding_4_bms_proxy_and_signal_lineage": {
        "pre_proxy_commands": ["CHWC_VLV_DM", "HC_VLV_DM", "OA_DMPR_DM", "RA_DMPR_DM"],
        "critical_defect": "MA_TEMP duplicates SA_TEMP on both AHU9 and AHU10 (delta = 0.00 C). Direct inclusion creates catastrophic target leakage. Must use thermodynamic MA_TEMP_EST.",
        "proxy_nature": "Empirical evidence confirms CHWC_VLV_DM logs the controller pre-proxy command (5-10%), not the injected stuck magnitude (88%). However, post-proxy actuator feedback is not logged in the BMS."
    },
    "finding_5_breakdown_of_gain_and_failure": {
        "ahu9_gain_analysis": {
            "reported_gain": "+3 events (6/36 -> 9/36)",
            "gained_event_ids": [287, 288, 289],
            "nature": "SIMULTANEOUS MULTI-INJECTION: All 3 events started concurrently on 2013-11-08 at 14:32:34 (OA Damper 76%, Zone Drift -2C, OA Damper 49%).",
            "physical_interpretation": "U_ONLY detected 1 single physical fault episode, which was counted as 3 detected events in the spreadsheet due to 3 concurrent entries. Unique physical episodes detected: T_ONLY=3, U_ONLY=1, T_PLUS_U=4."
        },
        "ahu10_failure_analysis": {
            "reported_result": "0 gained events (T_ONLY=6/36, U_ONLY=0/36, T_PLUS_U=6/36, FAR increased from 1.28% to 3.83%).",
            "causes": [
                "Contamination of AHU10 Train (12 faults) and Val (9 faults) due to unmasked split.",
                "Regime mismatch: Train valve command was near-zero (mean 1.6%) during cool weather, while Val/Test had active cooling (valve ~15%), causing static Ridge to fail with R2 = -8.42.",
                "Overly conservative threshold (tau_z = 5.0) with 10-of-15 persistence suppressed transient fault deviations."
            ]
        }
    },
    "finding_6_external_dataset_accessibility": {
        "target": "RBC-Nesbitt (Drexel University, Scientific Data 2026, Figshare DOI 10.6084/m9.figshare.29297999)",
        "archive_size": "928.68 MB (Public_ScientificData_AHUFaults.zip)",
        "accessibility_status": "Figshare download URL (ndownloader.figshare.com/files/57268553) redirects to Amazon S3 with 10-second signed tokens, returning 403 Forbidden on programmatic requests.",
        "gate_8b_4_strategy": "Document status honestly. If external download remains blocked, evaluate local adaptation across AHU-09 and AHU-10 with clean masks and mark external building transfer protocol as NOT_EVALUABLE_REMOTE_403."
    },
    "gate_decision": {
        "verdict": "CONDITIONAL_GO",
        "action_items_for_gate_8b_1": [
            "Create a clean masked split for AHU-10 using CSIROTemporalSplitter(embargo_minutes=60) to eliminate fault contamination.",
            "Implement gap-aware dynamic state tracking (reset upon delta_t > 120s or fan ON transition).",
            "Develop dynamic Ridge with lags, ARX, and regime-specific residuals.",
            "Evaluate physical episodes alongside spreadsheet row events."
        ]
    }
}

with open("research/runs/stage8b_0_audit.json", "w", encoding="utf-8") as f:
    json.dump(audit_data, f, indent=2, ensure_ascii=False)

print("Saved research/runs/stage8b_0_audit.json successfully.")
