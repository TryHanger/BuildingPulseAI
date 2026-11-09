from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Set
import numpy as np
import pandas as pd

@dataclass
class DiagnosticEvidence:
    evidence_id: str
    component: str  # e.g. "FAN", "COOLING_COIL", "OUTDOOR_DAMPER", "SYSTEM"
    measured_channels: List[str]
    available: bool
    applicable: bool
    value: Optional[float]
    unit: str
    threshold: Optional[float]
    direction: Optional[str]  # "ABOVE", "BELOW", "NORMAL", "UNKNOWN"
    supports: List[str]       # Class labels supported by this evidence
    contradicts: List[str]    # Class labels contradicted / refuted by this evidence
    reason_if_unavailable: Optional[str] = None
    source: str = "observed"  # "observed", "derived", "model_residual"
    tracking_status: Optional[str] = None  # "SUPPORTS", "CONTRADICTS_CONDITIONALLY", "INCONCLUSIVE", "UNAVAILABLE"
    tracking_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class EvidenceEvaluator:
    """
    Computes structured physical and model evidence for a given diagnostic window
    respecting allowed channels of the active observability profile.
    """
    def __init__(self, allowed_channels: Set[str]):
        self.allowed_channels = set(allowed_channels)

    def evaluate_window_evidence(
        self,
        df_window: pd.DataFrame,
        vs_predicted_sa_temp: Optional[np.ndarray] = None,
        vs_residual_threshold: float = 0.919,
        operating_mask: Optional[np.ndarray] = None
    ) -> List[DiagnosticEvidence]:
        evidence_list: List[DiagnosticEvidence] = []

        # 1. Operating Fan Evidence
        has_sf_spd = "SF_SPD_DM" in self.allowed_channels and "SF_SPD_DM" in df_window.columns
        if has_sf_spd:
            sf_mean = float(df_window["SF_SPD_DM"].mean())
            fan_on = bool(sf_mean >= 0.5)
            evidence_list.append(DiagnosticEvidence(
                evidence_id="operating_fan_status",
                component="FAN",
                measured_channels=["SF_SPD_DM"],
                available=True,
                applicable=True,
                value=round(sf_mean, 2),
                unit="binary_command",
                threshold=0.5,
                direction="NORMAL" if fan_on else "BELOW",
                supports=["FAULT_FREE"] if fan_on else [],
                contradicts=[],
                source="observed"
            ))
        else:
            evidence_list.append(DiagnosticEvidence(
                evidence_id="operating_fan_status",
                component="FAN",
                measured_channels=["SF_SPD_DM"],
                available=False,
                applicable=False,
                value=None,
                unit="binary_command",
                threshold=0.5,
                direction=None,
                supports=[],
                contradicts=[],
                reason_if_unavailable="Канал SF_SPD_DM не входит в разрешенный профиль",
                source="observed"
            ))

        # 2. Virtual Sensor Residual Evidence
        has_sa_temp = "SA_TEMP" in self.allowed_channels and "SA_TEMP" in df_window.columns
        if has_sa_temp and vs_predicted_sa_temp is not None and len(vs_predicted_sa_temp) == len(df_window):
            valid_mask = (df_window["SA_TEMP"].notna().values &
                          (operating_mask if operating_mask is not None else np.ones(len(df_window), dtype=bool)))
            if np.any(valid_mask):
                sa_actual = df_window["SA_TEMP"].values[valid_mask]
                sa_pred = vs_predicted_sa_temp[valid_mask]
                residuals = sa_actual - sa_pred
                mean_res = float(np.mean(residuals))
                mean_abs_res = float(np.mean(np.abs(residuals)))
                direction = "ABOVE" if mean_res > vs_residual_threshold else (
                    "BELOW" if mean_res < -vs_residual_threshold else "NORMAL"
                )
                is_anom = mean_abs_res >= vs_residual_threshold

                evidence_list.append(DiagnosticEvidence(
                    evidence_id="virtual_sensor_residual",
                    component="SUPPLY",
                    measured_channels=["SA_TEMP"],
                    available=True,
                    applicable=True,
                    value=round(mean_abs_res, 3),
                    unit="degC",
                    threshold=round(vs_residual_threshold, 3),
                    direction=direction,
                    supports=["SENSOR_BIAS_SA", "COOLING_VALVE_STUCK", "OUTDOOR_DAMPER_STUCK"] if is_anom else ["FAULT_FREE"],
                    contradicts=["FAULT_FREE"] if is_anom else ["SENSOR_BIAS_SA", "COOLING_VALVE_STUCK"],
                    source="model_residual"
                ))
            else:
                evidence_list.append(DiagnosticEvidence(
                    evidence_id="virtual_sensor_residual",
                    component="SUPPLY",
                    measured_channels=["SA_TEMP"],
                    available=True,
                    applicable=False,
                    value=None,
                    unit="degC",
                    threshold=round(vs_residual_threshold, 3),
                    direction="UNKNOWN",
                    supports=[],
                    contradicts=[],
                    reason_if_unavailable="Нет активных рабочих точек в окне",
                    source="model_residual"
                ))
        else:
            evidence_list.append(DiagnosticEvidence(
                evidence_id="virtual_sensor_residual",
                component="SUPPLY",
                measured_channels=["SA_TEMP"],
                available=False,
                applicable=False,
                value=None,
                unit="degC",
                threshold=round(vs_residual_threshold, 3),
                direction=None,
                supports=[],
                contradicts=[],
                reason_if_unavailable="SA_TEMP отсутствует или прогноз модели не передан",
                source="model_residual"
            ))

        # 3. Cooling Valve Command vs Actual Feedback Discrepancy & Tracking Dynamics
        has_vlv_dm = "CHWC_VLV_DM" in self.allowed_channels and "CHWC_VLV_DM" in df_window.columns
        has_vlv_fb = "CHWC_VLV" in self.allowed_channels and "CHWC_VLV" in df_window.columns
        if has_vlv_dm and has_vlv_fb:
            vlv_dm = df_window["CHWC_VLV_DM"].dropna().values
            vlv_fb = df_window["CHWC_VLV"].dropna().values
            min_l = min(len(vlv_dm), len(vlv_fb))
            if min_l > 0:
                vlv_dm_slice = vlv_dm[:min_l]
                vlv_fb_slice = vlv_fb[:min_l]
                diff = np.abs(vlv_dm_slice - vlv_fb_slice)
                mean_diff = float(np.mean(diff))
                cmd_range = float(np.ptp(vlv_dm_slice))
                excitation_threshold = 0.15  # Minimum 15% command variation required for dynamic tracking verification

                # Scientific Tracking Logic:
                # Discrepancy >= 0.12 => Supports stuck/actuator fault
                # If cmd_range < 0.15 => INSUFFICIENT_ACTUATOR_EXCITATION (cannot refute stuck if command didn't move!)
                # If cmd_range >= 0.15 and mean_diff < 0.05 => CONTRADICTS_CONDITIONALLY (mechanical tracking confirmed under excitation; leakage not excluded)
                # Otherwise => INCONCLUSIVE (ambiguous/intermediate tracking error)
                if mean_diff >= 0.12:
                    tr_status = "SUPPORTS"
                    direction = "ABOVE"
                    supports_cls = ["COOLING_VALVE_STUCK"]
                    contradicts_cls = ["FAULT_FREE"]
                    tr_reason = f"Рассогласование положения клапана ({mean_diff*100:.1f}%) превышает порог 12%"
                elif cmd_range < excitation_threshold:
                    tr_status = "INCONCLUSIVE"
                    direction = "NORMAL"
                    supports_cls = []
                    contradicts_cls = []  # CANNOT refute stuck when actuator was not commanded to move!
                    tr_reason = f"Недостаточное возбуждение привода (диапазон команды {cmd_range*100:.1f}% < 15%). Совпадение положения при постоянной команде не исключает заклинивание."
                elif mean_diff < 0.05:
                    tr_status = "CONTRADICTS_CONDITIONALLY"
                    direction = "NORMAL"
                    supports_cls = ["SENSOR_BIAS_SA"]
                    contradicts_cls = ["COOLING_VALVE_STUCK"]  # conditional counter-evidence to mechanical stuck; seat leakage not excluded
                    tr_reason = f"Динамическое следование подтверждено (диапазон команды {cmd_range*100:.1f}%, ошибка {mean_diff*100:.1f}% < 5%). Заклинивание привода маловероятно при активном ходе (утечка через седло не исключена)."
                else:
                    tr_status = "INCONCLUSIVE"
                    direction = "NORMAL"
                    supports_cls = []
                    contradicts_cls = []
                    tr_reason = f"Промежуточная ошибка слежения привода ({mean_diff*100:.1f}%). Свидетельство неоднозначно."

                evidence_list.append(DiagnosticEvidence(
                    evidence_id="valve_actuator_discrepancy",
                    component="COOLING_COIL",
                    measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
                    available=True,
                    applicable=True,
                    value=round(mean_diff, 3),
                    unit="fraction_0_1",
                    threshold=0.12,
                    direction=direction,
                    supports=supports_cls,
                    contradicts=contradicts_cls,
                    source="observed",
                    tracking_status=tr_status,
                    tracking_reason=tr_reason
                ))
            else:
                evidence_list.append(DiagnosticEvidence(
                    evidence_id="valve_actuator_discrepancy",
                    component="COOLING_COIL",
                    measured_channels=["CHWC_VLV_DM", "CHWC_VLV"],
                    available=True,
                    applicable=False,
                    value=None,
                    unit="fraction_0_1",
                    threshold=0.12,
                    direction=None,
                    supports=[],
                    contradicts=[],
                    source="observed",
                    tracking_status="INCONCLUSIVE",
                    tracking_reason="Нет валидных данных телеметрии клапана в окне"
                ))
        else:
            evidence_list.append(DiagnosticEvidence(
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
                reason_if_unavailable="Канал обратной связи CHWC_VLV отсутствует в текущем профиле",
                source="observed",
                tracking_status="UNAVAILABLE",
                tracking_reason="Датчик положения штока клапана недоступен"
            ))

        # 4. Outdoor Damper Command vs Actual Feedback Discrepancy & Tracking Dynamics
        has_dmpr_dm = "OA_DMPR_DM" in self.allowed_channels and "OA_DMPR_DM" in df_window.columns
        has_dmpr_fb = "OA_DMPR" in self.allowed_channels and "OA_DMPR" in df_window.columns
        if has_dmpr_dm and has_dmpr_fb:
            dmpr_dm = df_window["OA_DMPR_DM"].dropna().values
            dmpr_fb = df_window["OA_DMPR"].dropna().values
            min_l = min(len(dmpr_dm), len(dmpr_fb))
            if min_l > 0:
                dmpr_dm_slice = dmpr_dm[:min_l]
                dmpr_fb_slice = dmpr_fb[:min_l]
                diff = np.abs(dmpr_dm_slice - dmpr_fb_slice)
                mean_diff = float(np.mean(diff))
                cmd_range = float(np.ptp(dmpr_dm_slice))
                excitation_threshold = 0.15

                if mean_diff >= 0.12:
                    tr_status = "SUPPORTS"
                    direction = "ABOVE"
                    supports_cls = ["OUTDOOR_DAMPER_STUCK"]
                    contradicts_cls = ["FAULT_FREE"]
                    tr_reason = f"Рассогласование положения заслонки ({mean_diff*100:.1f}%) превышает порог 12%"
                elif cmd_range < excitation_threshold:
                    tr_status = "INCONCLUSIVE"
                    direction = "NORMAL"
                    supports_cls = []
                    contradicts_cls = []
                    tr_reason = f"Недостаточное возбуждение привода заслонки (диапазон команды {cmd_range*100:.1f}% < 15%). Заклинивание не исключено."
                elif mean_diff < 0.05:
                    tr_status = "CONTRADICTS_CONDITIONALLY"
                    direction = "NORMAL"
                    supports_cls = ["SENSOR_BIAS_SA"]
                    contradicts_cls = ["OUTDOOR_DAMPER_STUCK"]
                    tr_reason = f"Динамическое следование заслонки подтверждено (диапазон {cmd_range*100:.1f}%, ошибка {mean_diff*100:.1f}% < 5%). Заклинивание привода маловероятно."
                else:
                    tr_status = "INCONCLUSIVE"
                    direction = "NORMAL"
                    supports_cls = []
                    contradicts_cls = []
                    tr_reason = f"Промежуточная ошибка слежения заслонки ({mean_diff*100:.1f}%). Свидетельство неоднозначно."

                evidence_list.append(DiagnosticEvidence(
                    evidence_id="damper_actuator_discrepancy",
                    component="OUTDOOR_DAMPER",
                    measured_channels=["OA_DMPR_DM", "OA_DMPR"],
                    available=True,
                    applicable=True,
                    value=round(mean_diff, 3),
                    unit="fraction_0_1",
                    threshold=0.12,
                    direction=direction,
                    supports=supports_cls,
                    contradicts=contradicts_cls,
                    source="observed",
                    tracking_status=tr_status,
                    tracking_reason=tr_reason
                ))
            else:
                evidence_list.append(DiagnosticEvidence(
                    evidence_id="damper_actuator_discrepancy",
                    component="OUTDOOR_DAMPER",
                    measured_channels=["OA_DMPR_DM", "OA_DMPR"],
                    available=True,
                    applicable=False,
                    value=None,
                    unit="fraction_0_1",
                    threshold=0.12,
                    direction=None,
                    supports=[],
                    contradicts=[],
                    source="observed",
                    tracking_status="INCONCLUSIVE",
                    tracking_reason="Нет валидных данных телеметрии заслонки в окне"
                ))
        else:
            evidence_list.append(DiagnosticEvidence(
                evidence_id="damper_actuator_discrepancy",
                component="OUTDOOR_DAMPER",
                measured_channels=["OA_DMPR_DM", "OA_DMPR"],
                available=False,
                applicable=False,
                value=None,
                unit="fraction_0_1",
                threshold=0.12,
                direction=None,
                supports=[],
                contradicts=[],
                reason_if_unavailable="Канал обратной связи OA_DMPR отсутствует в текущем профиле",
                source="observed",
                tracking_status="UNAVAILABLE",
                tracking_reason="Датчик положения заслонки недоступен"
            ))

        # 5. Air Mixing Thermal Balance Consistency
        has_mix = all(ch in self.allowed_channels and ch in df_window.columns for ch in ["OA_TEMP", "RA_TEMP", "MA_TEMP"])
        if has_mix:
            oa = df_window["OA_TEMP"].dropna().values
            ra = df_window["RA_TEMP"].dropna().values
            ma = df_window["MA_TEMP"].dropna().values
            min_l = min(len(oa), len(ra), len(ma))
            if min_l > 0:
                oa_m = oa[:min_l]
                ra_m = ra[:min_l]
                ma_m = ma[:min_l]
                lower_b = np.minimum(oa_m, ra_m) - 1.5  # Tolerance 1.5°C
                upper_b = np.maximum(oa_m, ra_m) + 1.5
                violation = np.mean((ma_m < lower_b) | (ma_m > upper_b))
                is_violation = float(violation) > 0.10
                evidence_list.append(DiagnosticEvidence(
                    evidence_id="mixing_temperature_bounds",
                    component="MIXING",
                    measured_channels=["OA_TEMP", "RA_TEMP", "MA_TEMP"],
                    available=True,
                    applicable=True,
                    value=round(float(violation), 3),
                    unit="fraction_violations",
                    threshold=0.10,
                    direction="ABOVE" if is_violation else "NORMAL",
                    supports=["SENSOR_BIAS_SA"] if is_violation else [],
                    contradicts=[],
                    source="derived"
                ))
        else:
            evidence_list.append(DiagnosticEvidence(
                evidence_id="mixing_temperature_bounds",
                component="MIXING",
                measured_channels=["OA_TEMP", "RA_TEMP", "MA_TEMP"],
                available=False,
                applicable=False,
                value=None,
                unit="fraction_violations",
                threshold=0.10,
                direction=None,
                supports=[],
                contradicts=[],
                reason_if_unavailable="Один или несколько температурных каналов смешения отсутствуют",
                source="derived"
            ))

        # 6. Data Quality Signals (stuck sensor or NaN)
        nan_cols = [c for c in self.allowed_channels if c in df_window.columns and df_window[c].isna().sum() > 0.5 * len(df_window)]
        quality_ok = len(nan_cols) == 0
        evidence_list.append(DiagnosticEvidence(
            evidence_id="data_quality_integrity",
            component="SYSTEM",
            measured_channels=list(self.allowed_channels),
            available=True,
            applicable=True,
            value=0.0 if quality_ok else float(len(nan_cols)),
            unit="degraded_channels_count",
            threshold=0.0,
            direction="NORMAL" if quality_ok else "ABOVE",
            supports=["FAULT_FREE"] if quality_ok else [],
            contradicts=[],
            reason_if_unavailable=None if quality_ok else f"Пропуски в каналах: {', '.join(nan_cols)}",
            source="derived"
        ))

        return evidence_list
