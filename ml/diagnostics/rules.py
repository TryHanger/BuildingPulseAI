import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

class RuleDiagnosticEngine:
    """
    Deterministic rule-based baseline for fault-family localization (Basic profile only).
    Does NOT access ground truth labels or extended feedback channels.
    Outputs: FAULT_FREE, COOLING_VALVE_STUCK, OUTDOOR_DAMPER_STUCK, SENSOR_BIAS_SA, or UNRESOLVED.
    """
    def __init__(self, residual_threshold: float = 0.919):
        self.residual_threshold = residual_threshold

    def diagnose_row(self, row: pd.Series) -> Tuple[str, float, List[str], List[str]]:
        """
        Diagnoses a single operating minute based on physical features.
        Returns:
            candidate_class: str
            confidence_score: float (heuristic 0..1)
            supporting_evidence: List[str]
            missing_evidence: List[str]
        """
        res_abs = row.get("res_sa_abs", 0.0)
        res_signed = row.get("res_sa_signed", 0.0)
        res_std = row.get("res_sa_roll_std_15", 0.0)
        delta_t_chwc = row.get("delta_t_chwc", 0.0)
        delta_t_mixing = row.get("delta_t_mixing", 0.0)
        vlv_dm = row.get("chwc_vlv_dm", 0.0)
        dmpr_dm = row.get("oa_dmpr_dm", 0.0)
        oa_temp = row.get("oa_temp", 10.0)
        err_spt = row.get("error_spt", 0.0)

        missing_evidence = [
            "CHWC_VLV (прямой датчик положения штока клапана охлаждения недоступен в Basic)",
            "OA_DMPR (прямой датчик угла открытия заслонки наружного воздуха недоступен в Basic)"
        ]

        # 1. Normal state: residual within threshold
        if res_abs < self.residual_threshold:
            return (
                "FAULT_FREE",
                0.95,
                ["Температурная невязка виртуального датчика SA_TEMP находится в пределах нормы"],
                missing_evidence
            )

        # 2. Cooling Valve Stuck rule
        # Valve commanded closed (vlv_dm < 0.05), but strong cooling drop observed (delta_t_chwc > 1.5°C)
        if vlv_dm < 0.05 and delta_t_chwc > 1.5:
            return (
                "COOLING_VALVE_STUCK",
                0.85,
                [
                    f"Команда клапана охлаждения закрыта ({vlv_dm:.2f}), но наблюдается перепад на змеевике ΔT={delta_t_chwc:.1f}°C",
                    f"Отрицательная температурная невязка r_sa={res_signed:.2f}°C (переохлаждение)"
                ],
                missing_evidence
            )

        # Valve commanded open (vlv_dm > 0.4), but no cooling observed
        if vlv_dm > 0.4 and delta_t_chwc < 0.5:
            return (
                "COOLING_VALVE_STUCK",
                0.80,
                [
                    f"Команда клапана охлаждения открыта ({vlv_dm:.2f}), однако перепад температуры отсутствует (ΔT={delta_t_chwc:.1f}°C)",
                    f"Положительная невязка r_sa={res_signed:.2f}°C (недоохлаждение)"
                ],
                missing_evidence
            )

        # 3. Outdoor Damper Stuck rule
        # Cold weather (oa_temp < 5°C), damper commanded closed/min (dmpr_dm < 0.2), but excessive outdoor air intake
        if oa_temp < 5.0 and dmpr_dm < 0.2 and delta_t_mixing < 6.0 and res_signed < -1.5:
            return (
                "OUTDOOR_DAMPER_STUCK",
                0.78,
                [
                    f"Низкая наружная температура ({oa_temp:.1f}°C) при закрытой заслонке ({dmpr_dm:.2f})",
                    f"Температура смешения MA_TEMP приближена к наружной, резкое переохлаждение r_sa={res_signed:.2f}°C"
                ],
                missing_evidence
            )

        # 4. Sensor Bias rule
        # Valve closed, no cooling, but steady stationary offset with low variance
        if vlv_dm < 0.05 and abs(delta_t_chwc) < 1.0 and res_std < 0.4:
            return (
                "SENSOR_BIAS_SA",
                0.72,
                [
                    f"Тепловой баланс охладителя не нарушен (ΔT={delta_t_chwc:.1f}°C при закрытом клапане)",
                    f"Стационарное смещение температуры со стабильной невязкой r_sa={res_signed:.2f}°C (σ={res_std:.2f}°C)"
                ],
                missing_evidence
            )

        # 5. Ambiguous / Insufficient evidence
        return (
            "UNRESOLVED",
            0.40,
            [f"Зафиксирована аномалия (|r|={res_abs:.2f}°C), но физические свидетельства Basic-профиля недостаточны для локализации"],
            missing_evidence
        )

    def predict(self, X_diag: pd.DataFrame) -> List[str]:
        preds = []
        for _, row in X_diag.iterrows():
            cand, _, _, _ = self.diagnose_row(row)
            preds.append(cand)
        return preds
