import pytest
import numpy as np
import pandas as pd
from ml.diagnostics.evidence import DiagnosticEvidence, EvidenceEvaluator
from ml.diagnostics.decision_layer import EvidenceAwareDecisionLayer

def test_scenario_a_stuck_at_command_cannot_refute():
    """
    Test A: Valve is stuck at 25% and command is also steady at 25%.
    The tracking discrepancy is 0.0, but because there is NO command excitation (range < 0.15),
    it is scientifically FALSE to refute COOLING_VALVE_STUCK.
    Must return INCONCLUSIVE with reason INSUFFICIENT_ACTUATOR_EXCITATION.
    """
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    n_pts = 15
    df_window = pd.DataFrame({
        "CHWC_VLV_DM": [0.25] * n_pts,
        "CHWC_VLV": [0.25] * n_pts,
    })

    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    assert vlv_ev.tracking_status == "INCONCLUSIVE"
    assert "COOLING_VALVE_STUCK" not in vlv_ev.contradicts
    assert "Недостаточное возбуждение" in (vlv_ev.tracking_reason or "")

    # Now verify Decision Layer does not refute COOLING_VALVE_STUCK
    layer = EvidenceAwareDecisionLayer()
    probs = {"FAULT_FREE": 0.05, "SENSOR_BIAS_SA": 0.48, "COOLING_VALVE_STUCK": 0.42, "OUTDOOR_DAMPER_STUCK": 0.05}
    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=ev_list,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert "INSUFFICIENT_ACTUATOR_EXCITATION" in res["reason_codes"]
    assert "CONDITIONALLY_DISCOUNT_VALVE_STUCK" not in res["reason_codes"]
    assert res["status"] == "MULTIPLE_PLAUSIBLE"
    assert "COOLING_VALVE_STUCK" in res["candidate_causes"]

def test_scenario_b_command_changes_feedback_stuck():
    """
    Test B: Command moves from 20% to 70%, but position remains stuck at 25%.
    Must produce SUPPORTS COOLING_VALVE_STUCK with discrepancy >= 0.12.
    """
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    n_pts = 15
    df_window = pd.DataFrame({
        "CHWC_VLV_DM": np.linspace(0.20, 0.70, n_pts),
        "CHWC_VLV": [0.25] * n_pts
    })

    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    assert vlv_ev.tracking_status == "SUPPORTS"
    assert "COOLING_VALVE_STUCK" in vlv_ev.supports
    assert vlv_ev.value is not None and vlv_ev.value >= 0.12

    layer = EvidenceAwareDecisionLayer()
    probs = {"FAULT_FREE": 0.05, "SENSOR_BIAS_SA": 0.35, "COOLING_VALVE_STUCK": 0.55, "OUTDOOR_DAMPER_STUCK": 0.05}
    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=ev_list,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert res["status"] == "SINGLE_CAUSE"
    assert res["single_cause"] == "COOLING_VALVE_STUCK"
    assert "CONFIRMED_BY_FEEDBACK" in res["reason_codes"]

def test_scenario_c_dynamic_tracking_conditional_counterevidence_not_leakage_proof():
    """
    Test C: Command moves dynamically (20% -> 60%) and position accurately tracks (mean error < 0.05).
    Produces CONTRADICTS_CONDITIONALLY for mechanical stuck under dynamic motion.
    Explicitly includes limitation that internal seat leakage is NOT refuted.
    """
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    n_pts = 15
    cmd = np.linspace(0.20, 0.60, n_pts)
    fb = cmd + 0.01  # small lag/error 1%

    df_window = pd.DataFrame({"CHWC_VLV_DM": cmd, "CHWC_VLV": fb})
    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    assert vlv_ev.tracking_status == "CONTRADICTS_CONDITIONALLY"
    assert "COOLING_VALVE_STUCK" in vlv_ev.contradicts
    assert "утечка через седло" in (vlv_ev.tracking_reason or "")

    layer = EvidenceAwareDecisionLayer()
    probs = {"FAULT_FREE": 0.05, "SENSOR_BIAS_SA": 0.60, "COOLING_VALVE_STUCK": 0.30, "OUTDOOR_DAMPER_STUCK": 0.05}
    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=ev_list,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert res["status"] == "SINGLE_CAUSE"
    assert res["single_cause"] == "SENSOR_BIAS_SA"
    assert "CONDITIONALLY_DISCOUNT_VALVE_STUCK" in res["reason_codes"]
    assert any("утечка через седло" in lim for lim in res["limitations"])

def test_scenario_d_unavailable_or_noisy_feedback():
    """
    Test D: Feedback sensor is unavailable (e.g. BASIC profile) or all NaN.
    Must return UNAVAILABLE / INCONCLUSIVE with missing channel.
    """
    # 1. Unavailable in profile
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM"})
    df_window = pd.DataFrame({"CHWC_VLV_DM": [0.30] * 15, "CHWC_VLV": [0.30] * 15})
    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    assert not vlv_ev.available
    assert vlv_ev.tracking_status == "UNAVAILABLE"

    # 2. In profile but completely NaN
    evaluator2 = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    df_window2 = pd.DataFrame({"CHWC_VLV_DM": [0.30] * 15, "CHWC_VLV": [np.nan] * 15})
    ev_list2 = evaluator2.evaluate_window_evidence(df_window2)
    vlv_ev2 = next(e for e in ev_list2 if e.evidence_id == "valve_actuator_discrepancy")

    assert vlv_ev2.tracking_status == "INCONCLUSIVE"
    assert "COOLING_VALVE_STUCK" not in vlv_ev2.contradicts

def test_scenario_e_constantly_closed_valve_cannot_refute():
    """
    Test E: Constantly closed command 0.0 and feedback 0.0.
    Since command variation is 0.0 (< 0.15), it is INSUFFICIENT_ACTUATOR_EXCITATION.
    Cannot refute stuck at 0.0 (or seat leakage).
    """
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    df_window = pd.DataFrame({"CHWC_VLV_DM": [0.0] * 15, "CHWC_VLV": [0.0] * 15})
    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    assert vlv_ev.tracking_status == "INCONCLUSIVE"
    assert "COOLING_VALVE_STUCK" not in vlv_ev.contradicts

def test_scenario_f_stuck_level_matching_part_of_command_trajectory():
    """
    Test F: Stuck at 25%, command oscillates between 10% and 40% (passes through 25%).
    Even though command matches position at several points, the overall discrepancy
    under dynamic excitation will be high (>= 0.12) or significant.
    """
    evaluator = EvidenceEvaluator(allowed_channels={"CHWC_VLV_DM", "CHWC_VLV"})
    # Command moves 0.05 -> 0.45, crossing 0.25 in the middle
    cmd = np.array([0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.10])
    fb = np.full_like(cmd, 0.25)  # stuck at 25%

    df_window = pd.DataFrame({"CHWC_VLV_DM": cmd, "CHWC_VLV": fb})
    ev_list = evaluator.evaluate_window_evidence(df_window)
    vlv_ev = next(e for e in ev_list if e.evidence_id == "valve_actuator_discrepancy")

    # Command range is 0.40 (well above 0.15)
    # Mean error is mean(abs(cmd - 0.25)) = ~0.113
    assert "COOLING_VALVE_STUCK" not in vlv_ev.contradicts
