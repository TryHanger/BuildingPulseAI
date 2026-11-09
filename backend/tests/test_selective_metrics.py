import pytest
from ml.diagnostics.metrics_selective import (
    compute_selective_risk_at_threshold,
    compute_risk_coverage_curve,
    compute_set_metrics
)

def test_appendix_b_toy_benchmark():
    """
    Direct test of Appendix B benchmark numbers from BuildingPulse AI Master Prompt Stage 4.
    """
    y_true = ["SENSOR", "VALVE", "DAMPER", "VALVE", "SENSOR", "DAMPER"]
    y_pred = ["SENSOR", "VALVE", "VALVE", "VALVE", "DAMPER", "DAMPER"]
    scores = [0.95, 0.85, 0.80, 0.75, 0.60, 0.55]

    # Test tau = 0.80:
    # Accepted: W1 (0.95), W2 (0.85), W3 (0.80) -> 3 / 6 -> Coverage = 0.5
    # Errors: W3 is DAMPER != VALVE -> 1 error in 3 -> Risk = 1/3
    res_80 = compute_selective_risk_at_threshold(y_true, y_pred, scores, tau=0.80)
    assert res_80["coverage"] == pytest.approx(0.5, abs=1e-4)
    assert res_80["singletons_accepted"] == 3
    assert res_80["errors_in_accepted"] == 1
    assert res_80["risk"] == pytest.approx(1.0 / 3.0, abs=1e-4)

    # Test tau = 0.70:
    # Accepted: W1, W2, W3, W4 -> 4 / 6 -> Coverage = 2/3
    # Errors: W3 only -> 1 error in 4 -> Risk = 1/4 = 0.25
    res_70 = compute_selective_risk_at_threshold(y_true, y_pred, scores, tau=0.70)
    assert res_70["coverage"] == pytest.approx(2.0 / 3.0, abs=1e-4)
    assert res_70["singletons_accepted"] == 4
    assert res_70["errors_in_accepted"] == 1
    assert res_70["risk"] == pytest.approx(0.25, abs=1e-4)

    # Test tau = 0.50:
    # Accepted: all 6 -> Coverage = 1.0
    # Errors: W3 (DAMPER != VALVE), W5 (SENSOR != DAMPER) -> 2 errors in 6 -> Risk = 1/3
    res_50 = compute_selective_risk_at_threshold(y_true, y_pred, scores, tau=0.50)
    assert res_50["coverage"] == pytest.approx(1.0, abs=1e-4)
    assert res_50["singletons_accepted"] == 6
    assert res_50["errors_in_accepted"] == 2
    assert res_50["risk"] == pytest.approx(1.0 / 3.0, abs=1e-4)

    # Test tau = 0.99:
    # Accepted: 0 -> Coverage = 0.0, Risk MUST be None (undefined, not 0!)
    res_99 = compute_selective_risk_at_threshold(y_true, y_pred, scores, tau=0.99)
    assert res_99["coverage"] == 0.0
    assert res_99["singletons_accepted"] == 0
    assert res_99["risk"] is None

def test_candidate_set_metrics():
    """
    Verifies that multi-candidate sets are tracked in set coverage and mean set size,
    and not counted as singletons.
    """
    y_true = ["SENSOR", "VALVE", "DAMPER"]
    # W1: singleton correct, W2: multi-set containing true class, W3: candidate set size 3
    candidate_sets = [
        ["SENSOR"],
        ["VALVE", "DAMPER"],
        ["SENSOR", "VALVE", "DAMPER"]
    ]

    metrics = compute_set_metrics(y_true, candidate_sets)

    # All 3 contain the true label
    assert metrics["set_coverage"] == 1.0
    # Average set size: (1 + 2 + 3) / 3 = 2.0
    assert metrics["mean_set_size"] == pytest.approx(2.0, abs=1e-4)
    # Only 1 singleton out of 3: 1/3
    assert metrics["singleton_rate"] == pytest.approx(1.0 / 3.0, abs=1e-4)
    # 2 multi-candidate sets: 2/3
    assert metrics["multi_cause_rate"] == pytest.approx(2.0 / 3.0, abs=1e-4)
    assert metrics["unresolved_rate"] == 0.0
