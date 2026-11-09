from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd
from ml.virtual_sensor.features import fahrenheit_to_celsius

CANONICAL_BASIC_CHANNELS = [
    "OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP", "SA_TEMPSPT",
    "CHWC_VLV_DM", "OA_DMPR_DM", "RA_DMPR_DM",
    "SF_SPD_DM", "SF_CS", "RF_SPD_DM", "RF_CS",
    "SA_SP", "SA_SPSPT",
    "ZONE_TEMP_1", "ZONE_TEMP_2", "ZONE_TEMP_3", "ZONE_TEMP_4", "ZONE_TEMP_5"
]

@dataclass
class SensorProfileInfo:
    id: str
    display_name: str
    description: str
    allowed_channels: List[str]
    has_valve_feedback: bool
    has_damper_feedback: bool
    version: str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "description": self.description,
            "allowed_channels": self.allowed_channels,
            "has_valve_feedback": self.has_valve_feedback,
            "has_damper_feedback": self.has_damper_feedback,
            "version": self.version,
            "channel_count": len(self.allowed_channels)
        }

class SensorProfileRegistry:
    """
    Central registry for executable Sensor Observability Profiles.
    Enforces strict physical channel filtering:
    No module can access channels outside the active profile's whitelist.
    """
    _PROFILES: Dict[str, SensorProfileInfo] = {
        "BASIC": SensorProfileInfo(
            id="BASIC",
            display_name="Basic BMS (19 каналов)",
            description="Стандартная автоматизация без датчиков положения штоков приводов",
            allowed_channels=CANONICAL_BASIC_CHANNELS,
            has_valve_feedback=False,
            has_damper_feedback=False
        ),
        "BASIC_PLUS_VALVE": SensorProfileInfo(
            id="BASIC_PLUS_VALVE",
            display_name="Basic + Valve Feedback",
            description="Basic + прямой датчик положения штока клапана охлаждения CHWC_VLV",
            allowed_channels=CANONICAL_BASIC_CHANNELS + ["CHWC_VLV"],
            has_valve_feedback=True,
            has_damper_feedback=False
        ),
        "BASIC_PLUS_DAMPER": SensorProfileInfo(
            id="BASIC_PLUS_DAMPER",
            display_name="Basic + Damper Feedback",
            description="Basic + прямой датчик положения заслонки наружного воздуха OA_DMPR",
            allowed_channels=CANONICAL_BASIC_CHANNELS + ["OA_DMPR"],
            has_valve_feedback=False,
            has_damper_feedback=True
        ),
        "BASIC_PLUS_BOTH": SensorProfileInfo(
            id="BASIC_PLUS_BOTH",
            display_name="Basic + Both Actuators",
            description="Basic + обратная связь клапана CHWC_VLV и заслонки OA_DMPR",
            allowed_channels=CANONICAL_BASIC_CHANNELS + ["CHWC_VLV", "OA_DMPR"],
            has_valve_feedback=True,
            has_damper_feedback=True
        ),
        "FULL": SensorProfileInfo(
            id="FULL",
            display_name="Full Observability",
            description="Полная инструментальная оснащенность исследовательской лаборатории",
            allowed_channels=CANONICAL_BASIC_CHANNELS + [
                "CHWC_VLV", "OA_DMPR", "RA_DMPR", "SF_SPD", "SF_WAT",
                "RF_SPD", "RF_WAT", "OA_CFM", "RA_CFM", "SA_CFM", "SYS_CTL"
            ],
            has_valve_feedback=True,
            has_damper_feedback=True
        )
    }

    @classmethod
    def list_profiles(cls) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in cls._PROFILES.values()]

    @classmethod
    def get_profile(cls, profile_id: str) -> SensorProfileInfo:
        p_id = profile_id.upper()
        if p_id not in cls._PROFILES:
            raise ValueError(f"Unknown sensor profile: '{profile_id}'. Valid: {list(cls._PROFILES.keys())}")
        return cls._PROFILES[p_id]

    @classmethod
    def get_allowed_channels(cls, profile_id: str) -> List[str]:
        return cls.get_profile(profile_id).allowed_channels

    @classmethod
    def filter_dataframe(cls, df: pd.DataFrame, profile_id: str) -> pd.DataFrame:
        """
        Creates an isolated DataFrame view containing ONLY allowed channels of the profile.
        Any hidden columns are strictly omitted.
        """
        allowed = set(cls.get_allowed_channels(profile_id))
        keep_cols = [c for c in df.columns if c in allowed]
        return df[keep_cols].copy()

def extract_profile_diagnostic_features(
    df: pd.DataFrame,
    vs_pred: np.ndarray,
    profile_id: str = "BASIC"
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Extracts profile-specific diagnostic features using strictly allowed channels.
    Guarantees:
      - Hidden channels for the profile are completely excluded.
      - If hidden columns exist in raw df, modifying them does NOT affect output.
    """
    profile = SensorProfileRegistry.get_profile(profile_id)
    # 1. Strictly filter DataFrame by profile whitelist
    df_isolated = SensorProfileRegistry.filter_dataframe(df, profile_id)

    # 2. Temperature normalization (°F -> °C if needed)
    for col in ["MA_TEMP", "OA_TEMP", "RA_TEMP", "SA_TEMP", "SA_TEMPSPT"]:
        if col in df_isolated.columns:
            if df_isolated[col].dropna().mean() > 30.0:
                df_isolated[col] = fahrenheit_to_celsius(df_isolated[col])

    n = len(df_isolated)
    sa_act = df_isolated["SA_TEMP"].values if "SA_TEMP" in df_isolated.columns else np.zeros(n)
    ma_temp = df_isolated["MA_TEMP"].values if "MA_TEMP" in df_isolated.columns else np.zeros(n)
    oa_temp = df_isolated["OA_TEMP"].values if "OA_TEMP" in df_isolated.columns else np.zeros(n)
    vlv_dm = df_isolated["CHWC_VLV_DM"].values if "CHWC_VLV_DM" in df_isolated.columns else np.zeros(n)
    dmpr_dm = df_isolated["OA_DMPR_DM"].values if "OA_DMPR_DM" in df_isolated.columns else np.zeros(n)
    spt = df_isolated["SA_TEMPSPT"].values if "SA_TEMPSPT" in df_isolated.columns else np.full(n, 12.8)

    # Base Basic features
    res_signed = sa_act - vs_pred
    res_abs = np.abs(res_signed)
    s_res = pd.Series(res_signed, index=df_isolated.index)
    res_roll_mean = s_res.rolling(window=15, min_periods=1).mean().values
    res_roll_std = s_res.rolling(window=15, min_periods=1).std().fillna(0.0).values

    delta_t_chwc = ma_temp - sa_act
    delta_t_mixing = ma_temp - oa_temp
    error_spt = sa_act - spt

    cooling_discrepancy = np.where(
        vlv_dm < 0.05,
        np.maximum(0.0, delta_t_chwc - 1.0),
        np.where(vlv_dm > 0.3, np.maximum(0.0, 3.0 * vlv_dm - delta_t_chwc), 0.0)
    )

    feat_dict: Dict[str, np.ndarray] = {
        "res_sa_signed": res_signed,
        "res_sa_abs": res_abs,
        "res_sa_roll_mean_15": res_roll_mean,
        "res_sa_roll_std_15": res_roll_std,
        "delta_t_chwc": delta_t_chwc,
        "delta_t_mixing": delta_t_mixing,
        "error_spt": error_spt,
        "chwc_vlv_dm": vlv_dm,
        "oa_dmpr_dm": dmpr_dm,
        "oa_temp": oa_temp,
        "cooling_demand_discrepancy": cooling_discrepancy
    }

    # Add Valve Feedback features if allowed by profile
    if profile.has_valve_feedback and "CHWC_VLV" in df_isolated.columns:
        vlv_fb = df_isolated["CHWC_VLV"].fillna(0.0).values
        vlv_pos_diff = np.abs(vlv_dm - vlv_fb)
        s_vlv_diff = pd.Series(vlv_pos_diff, index=df_isolated.index)
        vlv_pos_diff_roll = s_vlv_diff.rolling(window=15, min_periods=1).mean().values
        feat_dict["chwc_vlv_fb"] = vlv_fb
        feat_dict["vlv_pos_discrepancy"] = vlv_pos_diff
        feat_dict["vlv_pos_discrepancy_roll_15"] = vlv_pos_diff_roll

    # Add Damper Feedback features if allowed by profile
    if profile.has_damper_feedback and "OA_DMPR" in df_isolated.columns:
        dmpr_fb = df_isolated["OA_DMPR"].fillna(0.0).values
        dmpr_pos_diff = np.abs(dmpr_dm - dmpr_fb)
        s_dmpr_diff = pd.Series(dmpr_pos_diff, index=df_isolated.index)
        dmpr_pos_diff_roll = s_dmpr_diff.rolling(window=15, min_periods=1).mean().values
        feat_dict["oa_dmpr_fb"] = dmpr_fb
        feat_dict["dmpr_pos_discrepancy"] = dmpr_pos_diff
        feat_dict["dmpr_pos_discrepancy_roll_15"] = dmpr_pos_diff_roll

    # Add Full profile extra features if FULL
    if profile_id.upper() == "FULL":
        if "SF_WAT" in df_isolated.columns:
            feat_dict["sf_wat"] = df_isolated["SF_WAT"].fillna(0.0).values
        if "OA_CFM" in df_isolated.columns and "SA_CFM" in df_isolated.columns:
            sa_cfm = np.maximum(10.0, df_isolated["SA_CFM"].fillna(0.0).values)
            oa_cfm = df_isolated["OA_CFM"].fillna(0.0).values
            feat_dict["oa_cfm_ratio"] = oa_cfm / sa_cfm

    df_feats = pd.DataFrame(feat_dict, index=df_isolated.index)
    return df_feats, list(df_feats.columns)
