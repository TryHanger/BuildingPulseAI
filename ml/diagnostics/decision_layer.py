from typing import List, Dict, Any, Optional, Set
import numpy as np
from ml.diagnostics.evidence import DiagnosticEvidence

CANONICAL_FAULT_CLASSES = [
    "FAULT_FREE",
    "SENSOR_BIAS_SA",
    "COOLING_VALVE_STUCK",
    "OUTDOOR_DAMPER_STUCK"
]

class EvidenceAwareDecisionLayer:
    """
    Formal Evidence-Aware Decision Layer for AHU Diagnostics.

    Combines anomaly detection state, classifier posterior scores,
    physical domain evidence, channel observability profile, and data quality checks
    to yield interpretable diagnostic conclusions:
      - SINGLE_CAUSE
      - MULTIPLE_PLAUSIBLE
      - CAUSE_UNRESOLVED
      - NO_ANOMALY
      - AHU_OFF
      - INSUFFICIENT_DATA
      - OUT_OF_DOMAIN
    """
    def __init__(
        self,
        min_viable_prob: float = 0.20,
        singleton_decisive_margin: float = 0.40,
        singleton_high_prob: float = 0.80,
        valve_discrepancy_threshold: float = 0.12,
        damper_discrepancy_threshold: float = 0.12
    ):
        self.min_viable_prob = min_viable_prob
        self.singleton_decisive_margin = singleton_decisive_margin
        self.singleton_high_prob = singleton_high_prob
        self.valve_discrepancy_threshold = valve_discrepancy_threshold
        self.damper_discrepancy_threshold = damper_discrepancy_threshold

    def evaluate(
        self,
        domain_status: str,  # "VALIDATED" or "OUT_OF_DOMAIN"
        is_operating: bool,  # Fan running (SF_SPD_DM >= 0.5)
        anomaly_detected: bool,
        classifier_probs: Dict[str, float],
        evidence_list: List[DiagnosticEvidence],
        profile_id: str = "BASIC"
    ) -> Dict[str, Any]:
        """
        Executes formal decision evaluation for one diagnostic window.
        """
        reason_codes: List[str] = []
        limitations: List[str] = []
        missing_measurements: List[str] = []

        # 1. Gate: Domain Guard
        if domain_status != "VALIDATED":
            return {
                "status": "OUT_OF_DOMAIN",
                "single_cause": None,
                "candidate_causes": [],
                "scores": classifier_probs,
                "reason_codes": ["OUT_OF_DOMAIN_BENCHMARK"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": [],
                "limitations": ["Источник данных не прошел валидацию на совместимость с симуляционной моделью LBNL"]
            }

        # 2. Gate: Operating Mode (AHU OFF)
        if not is_operating:
            return {
                "status": "AHU_OFF",
                "single_cause": None,
                "candidate_causes": [],
                "scores": classifier_probs,
                "reason_codes": ["OPERATING_MODE_OFF"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": [],
                "limitations": ["Оборудование выключено (SF_SPD_DM < 0.5), диагностика не проводится во избежание ложных тревог"]
            }

        # 3. Gate: Data Quality Integrity
        quality_ev = next((e for e in evidence_list if e.evidence_id == "data_quality_integrity"), None)
        if quality_ev and quality_ev.direction == "ABOVE":
            reason_codes.append("DATA_QUALITY_DEGRADED")
            limitations.append("Качество данных снижено (обнаружены пропуски или искажения)")

        # 4. Gate: Anomaly Detection
        if not anomaly_detected:
            return {
                "status": "NO_ANOMALY",
                "single_cause": None,
                "candidate_causes": [],
                "scores": classifier_probs,
                "reason_codes": ["RESIDUAL_BELOW_THRESHOLD"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": [],
                "limitations": []
            }

        # 5. Fault Family Diagnostic Decision
        # Collect physical evidence regarding actuators
        valve_ev = next((e for e in evidence_list if e.evidence_id == "valve_actuator_discrepancy"), None)
        damper_ev = next((e for e in evidence_list if e.evidence_id == "damper_actuator_discrepancy"), None)

        if not valve_ev or not valve_ev.available:
            missing_measurements.append("CHWC_VLV")
        if not damper_ev or not damper_ev.available:
            missing_measurements.append("OA_DMPR")

        # Check direct actuator physical feedback evidence first (if available in profile)
        has_valve_feedback = (valve_ev is not None and valve_ev.available)
        has_damper_feedback = (damper_ev is not None and damper_ev.available)

        # Case A: Extended Profile with Valve Feedback
        if has_valve_feedback:
            valve_tr = getattr(valve_ev, "tracking_status", None)
            if valve_tr == "SUPPORTS" or (valve_ev.direction == "ABOVE" and (valve_ev.value or 0.0) >= self.valve_discrepancy_threshold):
                # Direct confirmation of valve stuck
                return {
                    "status": "SINGLE_CAUSE",
                    "single_cause": "COOLING_VALVE_STUCK",
                    "candidate_causes": ["COOLING_VALVE_STUCK"],
                    "scores": classifier_probs,
                    "reason_codes": ["CONFIRMED_BY_FEEDBACK", "CHWC_VLV_DISCREPANCY_DETECTED"],
                    "evidence": [e.to_dict() for e in evidence_list],
                    "missing_measurements": missing_measurements,
                    "limitations": []
                }
            elif valve_tr == "CONTRADICTS_CONDITIONALLY":
                # Dynamic tracking confirmed under command excitation (range >= 15%, error < 5%)
                reason_codes.append("TRACKING_CONFIRMED_UNDER_EXCITATION")
                reason_codes.append("CONDITIONALLY_DISCOUNT_VALVE_STUCK")
                limitations.append("Динамическое следование клапана подтверждено под нагрузкой; механическое заклинивание маловероятно (утечка через седло не исключена).")
            elif valve_tr == "INCONCLUSIVE" or (valve_ev.direction == "NORMAL" and (valve_ev.value or 0.0) < 0.05):
                # Actuator was not sufficiently excited or command was static: cannot refute stuck!
                reason_codes.append("INSUFFICIENT_ACTUATOR_EXCITATION")
                limitations.append("Недостаточное возбуждение команды клапана (диапазон < 15%): совпадение положения при постоянной команде не исключает заклинивание.")

        # Case B: Extended Profile with Damper Feedback
        if has_damper_feedback:
            damper_tr = getattr(damper_ev, "tracking_status", None)
            if damper_tr == "SUPPORTS" or (damper_ev.direction == "ABOVE" and (damper_ev.value or 0.0) >= self.damper_discrepancy_threshold):
                return {
                    "status": "SINGLE_CAUSE",
                    "single_cause": "OUTDOOR_DAMPER_STUCK",
                    "candidate_causes": ["OUTDOOR_DAMPER_STUCK"],
                    "scores": classifier_probs,
                    "reason_codes": ["CONFIRMED_BY_FEEDBACK", "OA_DMPR_DISCREPANCY_DETECTED"],
                    "evidence": [e.to_dict() for e in evidence_list],
                    "missing_measurements": missing_measurements,
                    "limitations": []
                }
            elif damper_tr == "CONTRADICTS_CONDITIONALLY":
                reason_codes.append("TRACKING_CONFIRMED_UNDER_EXCITATION")
                reason_codes.append("CONDITIONALLY_DISCOUNT_DAMPER_STUCK")
                limitations.append("Динамическое следование заслонки подтверждено под нагрузкой.")
            elif damper_tr == "INCONCLUSIVE" or (damper_ev.direction == "NORMAL" and (damper_ev.value or 0.0) < 0.05):
                reason_codes.append("INSUFFICIENT_DAMPER_EXCITATION")
                limitations.append("Недостаточное возбуждение команды заслонки: совпадение положения не исключает заклинивание.")

        # Case C: Multiclass Probabilistic & Evidence Arbitration
        fault_probs = {k: v for k, v in classifier_probs.items() if k != "FAULT_FREE"}
        if not fault_probs:
            return {
                "status": "CAUSE_UNRESOLVED",
                "single_cause": None,
                "candidate_causes": [],
                "scores": classifier_probs,
                "reason_codes": ["NO_FAULT_CANDIDATE_SCORES"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": missing_measurements,
                "limitations": ["Классификатор не вернул правдоподобных оценок для дефектов"]
            }

        sorted_faults = sorted(fault_probs.items(), key=lambda x: x[1], reverse=True)
        top_cls, top_p = sorted_faults[0]
        second_cls, second_p = sorted_faults[1] if len(sorted_faults) > 1 else (None, 0.0)
        margin = top_p - second_p

        # Filter viable candidates excluding conditionally discounted mechanical faults ONLY under verified dynamic excitation
        refuted_classes = set()
        if "CONDITIONALLY_DISCOUNT_VALVE_STUCK" in reason_codes:
            refuted_classes.add("COOLING_VALVE_STUCK")
        if "CONDITIONALLY_DISCOUNT_DAMPER_STUCK" in reason_codes:
            refuted_classes.add("OUTDOOR_DAMPER_STUCK")

        viable_candidates = [c for c, p in sorted_faults if p >= self.min_viable_prob and c not in refuted_classes]

        # If after conditional discount under dynamic excitation, exactly one viable candidate remains and has solid probability
        if len(viable_candidates) == 1 and viable_candidates[0] == top_cls and top_p >= 0.40:
            return {
                "status": "SINGLE_CAUSE",
                "single_cause": top_cls,
                "candidate_causes": [top_cls],
                "scores": classifier_probs,
                "reason_codes": reason_codes + ["SINGLE_UNREFUTED_CANDIDATE"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": missing_measurements,
                "limitations": limitations
            }

        # In BASIC profile without actuator feedback:
        # Check for structural ambiguity between SENSOR_BIAS_SA and COOLING_VALVE_STUCK
        if profile_id == "BASIC" and not has_valve_feedback:
            reason_codes.append("MISSING_VALVE_FEEDBACK")
            limitations.append("Датчик положения штока CHWC_VLV отсутствует в Basic: малое заклинивание клапана и смещение датчика температуры притока имеют схожие тепловые симптомы")

            # If both SENSOR_BIAS and COOLING_VALVE are viable or separation is low
            sensor_p = classifier_probs.get("SENSOR_BIAS_SA", 0.0)
            valve_p = classifier_probs.get("COOLING_VALVE_STUCK", 0.0)

            if sensor_p >= 0.20 and valve_p >= 0.20 and margin < self.singleton_decisive_margin:
                candidate_set = sorted(list(set(["SENSOR_BIAS_SA", "COOLING_VALVE_STUCK"] + [c for c, p in sorted_faults if p >= 0.25])))
                return {
                    "status": "MULTIPLE_PLAUSIBLE",
                    "single_cause": None,
                    "candidate_causes": candidate_set,
                    "scores": classifier_probs,
                    "reason_codes": reason_codes + ["AMBIGUOUS_WITHOUT_VALVE_FEEDBACK", "SIMILAR_SCORES"],
                    "evidence": [e.to_dict() for e in evidence_list],
                    "missing_measurements": missing_measurements,
                    "limitations": limitations
                }

        # If one class has overwhelming confidence and clear margin
        if top_p >= self.singleton_high_prob or (top_p >= 0.50 and margin >= self.singleton_decisive_margin):
            return {
                "status": "SINGLE_CAUSE",
                "single_cause": top_cls,
                "candidate_causes": [top_cls],
                "scores": classifier_probs,
                "reason_codes": reason_codes + ["DECISIVE_CLASSIFIER_CONFIDENCE"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": missing_measurements,
                "limitations": limitations
            }

        # If multiple viable candidates exist
        if len(viable_candidates) >= 2:
            return {
                "status": "MULTIPLE_PLAUSIBLE",
                "single_cause": None,
                "candidate_causes": viable_candidates,
                "scores": classifier_probs,
                "reason_codes": reason_codes + ["INSUFFICIENT_SEPARATION", "MULTIPLE_VIABLE_CANDIDATES"],
                "evidence": [e.to_dict() for e in evidence_list],
                "missing_measurements": missing_measurements,
                "limitations": limitations
            }

        # Otherwise: cause unresolved
        return {
            "status": "CAUSE_UNRESOLVED",
            "single_cause": None,
            "candidate_causes": [],
            "scores": classifier_probs,
            "reason_codes": reason_codes + ["LOW_CONFIDENCE"],
            "evidence": [e.to_dict() for e in evidence_list],
            "missing_measurements": missing_measurements,
            "limitations": limitations + ["Недостаточно подтверждающих свидетельств для надежной локализации"]
        }
