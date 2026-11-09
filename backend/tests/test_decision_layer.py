import pytest
import pandas as pd
import numpy as np
from ml.diagnostics.evidence import DiagnosticEvidence, EvidenceEvaluator
from ml.diagnostics.decision_layer import EvidenceAwareDecisionLayer

def test_domain_guard_blocks_unvalidated():
    layer = EvidenceAwareDecisionLayer()
    res = layer.evaluate(
        domain_status="OUT_OF_DOMAIN",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs={"SENSOR_BIAS_SA": 0.9},
        evidence_list=[],
        profile_id="BASIC"
    )
    assert res["status"] == "OUT_OF_DOMAIN"
    assert "OUT_OF_DOMAIN_BENCHMARK" in res["reason_codes"]
    assert res["single_cause"] is None

def test_ahu_off_gating():
    layer = EvidenceAwareDecisionLayer()
    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=False,
        anomaly_detected=True,
        classifier_probs={"COOLING_VALVE_STUCK": 0.8},
        evidence_list=[],
        profile_id="BASIC"
    )
    assert res["status"] == "AHU_OFF"
    assert "OPERATING_MODE_OFF" in res["reason_codes"]
    assert res["single_cause"] is None

def test_no_anomaly_detected():
    layer = EvidenceAwareDecisionLayer()
    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=False,
        classifier_probs={"FAULT_FREE": 0.95},
        evidence_list=[],
        profile_id="BASIC"
    )
    assert res["status"] == "NO_ANOMALY"
    assert res["single_cause"] is None

def test_basic_profile_structural_ambiguity():
    """
    In BASIC profile (without CHWC_VLV), when both SENSOR_BIAS and COOLING_VALVE
    have close probabilities, Decision Layer must NOT guess a singleton,
    and must return MULTIPLE_PLAUSIBLE with explanation.
    """
    layer = EvidenceAwareDecisionLayer()
    probs = {
        "FAULT_FREE": 0.05,
        "SENSOR_BIAS_SA": 0.48,
        "COOLING_VALVE_STUCK": 0.42,
        "OUTDOOR_DAMPER_STUCK": 0.05
    }
    # No actuator feedback in BASIC
    evidence = [
        DiagnosticEvidence(
            evidence_id="virtual_sensor_residual",
            component="SUPPLY",
            measured_channels=["SA_TEMP"],
            available=True,
            applicable=True,
            value=2.4,
            unit="degC",
            threshold=0.919,
            direction="ABOVE",
            supports=["SENSOR_BIAS_SA", "COOLING_VALVE_STUCK"],
            contradicts=["FAULT_FREE"]
        ),
        DiagnosticEvidence(
            evidence_id="valve_actuator_discrepancy",
            component="COOLING_COIL",
            measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
            available=False,
            applicable=False,
            value=None,
            unit="fraction_0_1",
            threshold=0.12,
            direction=None,
            supports=[],
            contradicts=[],
            reason_if_unavailable="Канал CHWC_VLV отсутствует в Basic"
        )
    ]

    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=evidence,
        profile_id="BASIC"
    )

    assert res["status"] == "MULTIPLE_PLAUSIBLE"
    assert res["single_cause"] is None
    assert "SENSOR_BIAS_SA" in res["candidate_causes"]
    assert "COOLING_VALVE_STUCK" in res["candidate_causes"]
    assert "AMBIGUOUS_WITHOUT_VALVE_FEEDBACK" in res["reason_codes"]
    assert "CHWC_VLV" in res["missing_measurements"]

def test_valve_feedback_disambiguates_single_cause():
    """
    When CHWC_VLV feedback is present (e.g. in BASIC_PLUS_VALVE) and shows a 25% discrepancy,
    it provides decisive physical confirmation of COOLING_VALVE_STUCK.
    """
    layer = EvidenceAwareDecisionLayer()
    probs = {
        "FAULT_FREE": 0.05,
        "SENSOR_BIAS_SA": 0.45,
        "COOLING_VALVE_STUCK": 0.45,
        "OUTDOOR_DAMPER_STUCK": 0.05
    }
    evidence = [
        DiagnosticEvidence(
            evidence_id="virtual_sensor_residual",
            component="SUPPLY",
            measured_channels=["SA_TEMP"],
            available=True,
            applicable=True,
            value=3.2,
            unit="degC",
            threshold=0.919,
            direction="ABOVE",
            supports=["SENSOR_BIAS_SA", "COOLING_VALVE_STUCK"],
            contradicts=["FAULT_FREE"]
        ),
        DiagnosticEvidence(
            evidence_id="valve_actuator_discrepancy",
            component="COOLING_COIL",
            measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
            available=True,
            applicable=True,
            value=0.25,
            unit="fraction_0_1",
            threshold=0.12,
            direction="ABOVE",
            supports=["COOLING_VALVE_STUCK"],
            contradicts=["SENSOR_BIAS_SA"]
        )
    ]

    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=evidence,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert res["status"] == "SINGLE_CAUSE"
    assert res["single_cause"] == "COOLING_VALVE_STUCK"
    assert "CONFIRMED_BY_FEEDBACK" in res["reason_codes"]
    assert "CHWC_VLV" not in res["missing_measurements"]

def test_valve_feedback_tracking_under_excitation():
    """
    When CHWC_VLV is available and dynamic excitation tracking is confirmed (tracking_status=CONTRADICTS_CONDITIONALLY),
    valve stuck is conditionally discounted under load, resolving ambiguity in favor of SENSOR_BIAS_SA
    while retaining the limitation that seat leakage is not excluded.
    """
    layer = EvidenceAwareDecisionLayer()
    probs = {
        "FAULT_FREE": 0.05,
        "SENSOR_BIAS_SA": 0.55,
        "COOLING_VALVE_STUCK": 0.35,
        "OUTDOOR_DAMPER_STUCK": 0.05
    }
    evidence = [
        DiagnosticEvidence(
            evidence_id="valve_actuator_discrepancy",
            component="COOLING_COIL",
            measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
            available=True,
            applicable=True,
            value=0.01,
            unit="fraction_0_1",
            threshold=0.12,
            direction="NORMAL",
            supports=["SENSOR_BIAS_SA"],
            contradicts=["COOLING_VALVE_STUCK"],
            tracking_status="CONTRADICTS_CONDITIONALLY"
        )
    ]

    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=evidence,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert res["status"] == "SINGLE_CAUSE"
    assert res["single_cause"] == "SENSOR_BIAS_SA"
    assert "TRACKING_CONFIRMED_UNDER_EXCITATION" in res["reason_codes"]
    assert "CONDITIONALLY_DISCOUNT_VALVE_STUCK" in res["reason_codes"]
    assert any("утечка через седло" in lim for lim in res["limitations"])

def test_valve_static_command_cannot_refute_stuck():
    """
    When command was static (e.g. tracking_status=INSUFFICIENT_ACTUATOR_EXCITATION),
    the decision layer CANNOT refute COOLING_VALVE_STUCK.
    If multiple causes are viable, it must return MULTIPLE_PLAUSIBLE.
    """
    layer = EvidenceAwareDecisionLayer()
    probs = {
        "FAULT_FREE": 0.05,
        "SENSOR_BIAS_SA": 0.45,
        "COOLING_VALVE_STUCK": 0.45,
        "OUTDOOR_DAMPER_STUCK": 0.05
    }
    evidence = [
        DiagnosticEvidence(
            evidence_id="valve_actuator_discrepancy",
            component="COOLING_COIL",
            measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
            available=True,
            applicable=True,
            value=0.00,
            unit="fraction_0_1",
            threshold=0.12,
            direction="NORMAL",
            supports=[],
            contradicts=[],
            tracking_status="INCONCLUSIVE"
        )
    ]

    res = layer.evaluate(
        domain_status="VALIDATED",
        is_operating=True,
        anomaly_detected=True,
        classifier_probs=probs,
        evidence_list=evidence,
        profile_id="BASIC_PLUS_VALVE"
    )

    assert res["status"] == "MULTIPLE_PLAUSIBLE"
    assert "COOLING_VALVE_STUCK" in res["candidate_causes"]
    assert "SENSOR_BIAS_SA" in res["candidate_causes"]
    assert "INSUFFICIENT_ACTUATOR_EXCITATION" in res["reason_codes"]

def test_baselines_b1_and_b2():
    from ml.diagnostics.confidence_baselines import ConfidenceOnlyBaseline, MarginEntropyBaseline

    b1 = ConfidenceOnlyBaseline(tau=0.70)
    # High confidence: accepts
    res_b1_high = b1.predict_window({"SENSOR_BIAS_SA": 0.75, "COOLING_VALVE_STUCK": 0.25})
    assert res_b1_high["status"] == "SINGLE_CAUSE"
    assert res_b1_high["single_cause"] == "SENSOR_BIAS_SA"

    # Low confidence: abstains
    res_b1_low = b1.predict_window({"SENSOR_BIAS_SA": 0.55, "COOLING_VALVE_STUCK": 0.45})
    assert res_b1_low["status"] == "CAUSE_UNRESOLVED"
    assert res_b1_low["single_cause"] is None

    b2 = MarginEntropyBaseline(margin_delta=0.30, max_entropy=0.85)
    # Decisive margin: accepts
    res_b2_decisive = b2.predict_window({"SENSOR_BIAS_SA": 0.70, "COOLING_VALVE_STUCK": 0.20, "OUTDOOR_DAMPER_STUCK": 0.10})
    assert res_b2_decisive["status"] == "SINGLE_CAUSE"

    # Small margin, multiple viable: returns MULTIPLE_PLAUSIBLE
    res_b2_ambiguous = b2.predict_window({"SENSOR_BIAS_SA": 0.45, "COOLING_VALVE_STUCK": 0.40, "OUTDOOR_DAMPER_STUCK": 0.15})
    assert res_b2_ambiguous["status"] == "MULTIPLE_PLAUSIBLE"
    assert "SENSOR_BIAS_SA" in res_b2_ambiguous["candidate_causes"]
    assert "COOLING_VALVE_STUCK" in res_b2_ambiguous["candidate_causes"]

