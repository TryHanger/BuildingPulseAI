from typing import List, Dict, Any, Optional, Tuple, Sequence
import numpy as np
import pandas as pd

def compute_selective_risk_at_threshold(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    scores: Sequence[float],
    tau: float,
    is_singleton: Optional[Sequence[bool]] = None
) -> Dict[str, Optional[float]]:
    """
    Computes Selective Coverage and Selective Risk at a single threshold tau.

    Parameters:
        y_true: True class labels for detected fault instances (size |D|).
        y_pred: Predicted class labels (size |D|).
        scores: Selectivity scores / confidence for singleton decision (size |D|).
        tau: Threshold for accepting a singleton prediction.
        is_singleton: Boolean mask indicating whether the model returned a singleton
                      (e.g., False if MULTIPLE_PLAUSIBLE or CAUSE_UNRESOLVED).
                      If None, any prediction with score >= tau is considered a candidate singleton.

    Returns:
        Dict with keys:
            - coverage: |A_tau| / |D|
            - risk: incorrect_single / |A_tau| (or None if |A_tau| == 0)
            - total_detected: |D|
            - singletons_accepted: |A_tau|
            - errors_in_accepted: int
    """
    n_total = len(y_true)
    if n_total == 0:
        return {
            "coverage": 0.0,
            "risk": None,
            "total_detected": 0,
            "singletons_accepted": 0,
            "errors_in_accepted": 0
        }

    # Identify accepted singletons
    accepted_mask = []
    for i in range(n_total):
        score_ok = (scores[i] >= tau)
        singleton_ok = is_singleton[i] if is_singleton is not None else True
        accepted_mask.append(score_ok and singleton_ok)

    accepted_mask = np.array(accepted_mask, dtype=bool)
    n_accepted = int(np.sum(accepted_mask))

    coverage = float(n_accepted / n_total)

    if n_accepted == 0:
        return {
            "coverage": 0.0,
            "risk": None,  # Undefined when coverage is zero, NOT 0!
            "total_detected": n_total,
            "singletons_accepted": 0,
            "errors_in_accepted": 0
        }

    # Count errors in accepted singletons
    errors = 0
    for i in range(n_total):
        if accepted_mask[i]:
            if y_pred[i] != y_true[i]:
                errors += 1

    risk = float(errors / n_accepted)

    return {
        "coverage": round(coverage, 6),
        "risk": round(risk, 6),
        "total_detected": n_total,
        "singletons_accepted": n_accepted,
        "errors_in_accepted": errors
    }

def compute_risk_coverage_curve(
    y_true: Sequence[str],
    y_pred: Sequence[str],
    scores: Sequence[float],
    thresholds: Sequence[float],
    is_singleton: Optional[Sequence[bool]] = None
) -> List[Dict[str, Any]]:
    """
    Generates the Risk-Coverage curve across multiple thresholds.
    """
    curve = []
    for tau in thresholds:
        res = compute_selective_risk_at_threshold(
            y_true=y_true,
            y_pred=y_pred,
            scores=scores,
            tau=tau,
            is_singleton=is_singleton
        )
        res["threshold"] = round(float(tau), 4)
        curve.append(res)
    return curve

def compute_set_metrics(
    y_true: Sequence[str],
    candidate_sets: Sequence[Sequence[str]]
) -> Dict[str, float]:
    """
    Computes multi-cause / hypothesis candidate set metrics:
    - SetCoverage: proportion of instances where y_true in candidate_set
    - MeanSetSize: average number of candidates in candidate_set
    - SingletonRate: proportion of sets with size == 1
    - MultiCauseRate: proportion of sets with size >= 2
    - UnresolvedRate: proportion of sets with size == 0
    """
    n = len(y_true)
    if n == 0:
        return {
            "set_coverage": 0.0,
            "mean_set_size": 0.0,
            "singleton_rate": 0.0,
            "multi_cause_rate": 0.0,
            "unresolved_rate": 0.0
        }

    in_set_count = 0
    sizes = []
    singleton_count = 0
    multi_count = 0
    unresolved_count = 0

    for yt, c_set in zip(y_true, candidate_sets):
        s_len = len(c_set)
        sizes.append(s_len)
        if yt in c_set:
            in_set_count += 1
        if s_len == 1:
            singleton_count += 1
        elif s_len >= 2:
            multi_count += 1
        else:
            unresolved_count += 1

    return {
        "set_coverage": round(float(in_set_count / n), 4),
        "mean_set_size": round(float(np.mean(sizes)), 4),
        "singleton_rate": round(float(singleton_count / n), 4),
        "multi_cause_rate": round(float(multi_count / n), 4),
        "unresolved_rate": round(float(unresolved_count / n), 4)
    }

def compute_end_to_end_metrics(
    total_eligible_fault_windows: int,
    detected_fault_windows: int,
    correctly_single_localized_windows: int,
    candidate_sets: Sequence[Sequence[str]],
    y_true: Sequence[str],
    normal_windows_total: int = 0,
    normal_windows_false_alarms: int = 0
) -> Dict[str, Any]:
    """
    Computes end-to-end diagnostic pipeline metrics.
    """
    f = total_eligible_fault_windows
    d = detected_fault_windows
    c = correctly_single_localized_windows

    det_recall = float(d / f) if f > 0 else 0.0
    yield_correct = float(c / f) if f > 0 else 0.0
    fa_rate = float(normal_windows_false_alarms / normal_windows_total) if normal_windows_total > 0 else 0.0

    set_stats = compute_set_metrics(y_true, candidate_sets)

    return {
        "total_fault_windows": f,
        "detected_fault_windows": d,
        "detection_recall": round(det_recall, 4),
        "correct_single_localized": c,
        "end_to_end_correct_single_yield": round(yield_correct, 4),
        "false_alarm_rate_on_normal": round(fa_rate, 4),
        "normal_windows_evaluated": normal_windows_total,
        "normal_false_alarms": normal_windows_false_alarms,
        **set_stats
    }
