from typing import List, Dict, Any, Optional, Sequence
import numpy as np

class ConfidenceOnlyBaseline:
    """
    Baseline B1: Rejection policy based solely on maximum class probability (confidence).
    Accepts a single diagnosis if max_c P(c) >= tau.
    Otherwise abstains with CAUSE_UNRESOLVED.
    """
    def __init__(self, tau: float = 0.50):
        self.tau = tau

    def predict_window(
        self,
        class_probs: Dict[str, float]
    ) -> Dict[str, Any]:
        if not class_probs:
            return {
                "status": "CAUSE_UNRESOLVED",
                "single_cause": None,
                "candidate_causes": [],
                "confidence_score": 0.0,
                "policy": "B1_CONFIDENCE_ONLY"
            }

        sorted_items = sorted(class_probs.items(), key=lambda x: x[1], reverse=True)
        top_class, top_prob = sorted_items[0]

        if top_prob >= self.tau:
            return {
                "status": "SINGLE_CAUSE",
                "single_cause": top_class,
                "candidate_causes": [top_class],
                "confidence_score": round(float(top_prob), 4),
                "policy": "B1_CONFIDENCE_ONLY"
            }
        else:
            return {
                "status": "CAUSE_UNRESOLVED",
                "single_cause": None,
                "candidate_causes": [],
                "confidence_score": round(float(top_prob), 4),
                "policy": "B1_CONFIDENCE_ONLY"
            }

class MarginEntropyBaseline:
    """
    Baseline B2: Rejection policy based on separation margin (P(1) - P(2)) and entropy.
    Accepts a single diagnosis if margin >= delta and normalized entropy <= eta.
    Returns MULTIPLE_PLAUSIBLE if top candidates are viable but separation is insufficient.
    Otherwise abstains with CAUSE_UNRESOLVED.
    """
    def __init__(self, margin_delta: float = 0.30, max_entropy: float = 0.85):
        self.margin_delta = margin_delta
        self.max_entropy = max_entropy

    def predict_window(
        self,
        class_probs: Dict[str, float]
    ) -> Dict[str, Any]:
        if not class_probs:
            return {
                "status": "CAUSE_UNRESOLVED",
                "single_cause": None,
                "candidate_causes": [],
                "margin": 0.0,
                "entropy": 1.0,
                "policy": "B2_MARGIN_ENTROPY"
            }

        sorted_items = sorted(class_probs.items(), key=lambda x: x[1], reverse=True)
        top_class, top_prob = sorted_items[0]
        second_prob = sorted_items[1][1] if len(sorted_items) > 1 else 0.0

        margin = float(top_prob - second_prob)

        # Compute normalized entropy
        probs = np.array([max(1e-12, v) for v in class_probs.values()])
        probs = probs / np.sum(probs)
        raw_ent = -np.sum(probs * np.log(probs))
        max_ent = np.log(len(probs)) if len(probs) > 1 else 1.0
        norm_entropy = float(raw_ent / max_ent)

        if margin >= self.margin_delta and norm_entropy <= self.max_entropy:
            return {
                "status": "SINGLE_CAUSE",
                "single_cause": top_class,
                "candidate_causes": [top_class],
                "margin": round(margin, 4),
                "entropy": round(norm_entropy, 4),
                "policy": "B2_MARGIN_ENTROPY"
            }
        elif len(sorted_items) >= 2 and sorted_items[1][1] >= 0.20:
            # Plausible competing candidates
            candidates = [c for c, p in sorted_items if p >= 0.20]
            return {
                "status": "MULTIPLE_PLAUSIBLE",
                "single_cause": None,
                "candidate_causes": candidates,
                "margin": round(margin, 4),
                "entropy": round(norm_entropy, 4),
                "policy": "B2_MARGIN_ENTROPY"
            }
        else:
            return {
                "status": "CAUSE_UNRESOLVED",
                "single_cause": None,
                "candidate_causes": [],
                "margin": round(margin, 4),
                "entropy": round(norm_entropy, 4),
                "policy": "B2_MARGIN_ENTROPY"
            }
