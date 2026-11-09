"""
Channel Semantics and Classification Module.
Strictly validates BMS channels for CSIRO AHU9 and AHU10.
Prevents data leakage, proxy contamination, and duplicate channel usage.
"""

from enum import Enum
from typing import Dict, List, Set


class ChannelSemanticType(str, Enum):
    OBSERVED_PHYSICAL_SENSOR = "OBSERVED_PHYSICAL_SENSOR"
    CONTROLLER_OUTPUT_PRE_PROXY = "CONTROLLER_OUTPUT_PRE_PROXY"
    ACTUATOR_COMMAND_POST_PROXY = "ACTUATOR_COMMAND_POST_PROXY"
    ACTUATOR_FEEDBACK = "ACTUATOR_FEEDBACK"
    FAULT_INJECTION_PARAMETER = "FAULT_INJECTION_PARAMETER"
    OPERATING_STATE = "OPERATING_STATE"
    SETPOINT = "SETPOINT"
    DERIVED_PROXY = "DERIVED_PROXY"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


# Canonical Semantic Map for CSIRO AHU9 / AHU10 Channels
CSIRO_CHANNEL_SEMANTICS: Dict[str, ChannelSemanticType] = {
    # Physical sensors
    "SA_TEMP": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "OA_TEMP": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "RA_TEMP": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "SA_SP": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "SA_RH": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "RA_RH": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "ZONE_TEMP_1": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "ZONE_TEMP_2": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,
    "ZONE_TEMP_3": ChannelSemanticType.OBSERVED_PHYSICAL_SENSOR,

    # Setpoints
    "SA_TEMPSPT": ChannelSemanticType.SETPOINT,

    # Controller Pre-Proxy Outputs
    "CHWC_VLV_DM": ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY,
    "HC_VLV_DM": ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY,
    "OA_DMPR_DM": ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY,
    "RA_DMPR_DM": ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY,
    "SF_CS": ChannelSemanticType.CONTROLLER_OUTPUT_PRE_PROXY,

    # Operational status
    "SF_SPD_DM": ChannelSemanticType.OPERATING_STATE,

    # Duplicates / Derived / Banned
    "MA_TEMP": ChannelSemanticType.DUPLICATE,  # In CSIRO MA_TEMP == SA_TEMP identically!
    "AVG_ZONE_TEMP": ChannelSemanticType.DERIVED_PROXY,
}

# Strictly allowed exogenous context features for u_hat model
ALLOWED_EXOGENOUS_FEATURES: List[str] = [
    "OA_TEMP",
    "RA_TEMP",
    "SA_TEMPSPT",
    "T_target_diff",   # RA_TEMP - SA_TEMPSPT
    "T_oa_sa_diff",    # OA_TEMP - SA_TEMPSPT
    "hour_sin",
    "hour_cos",
    "SF_CS",
]

# Strictly banned channels from any feature matrix X
BANNED_CHANNELS: Set[str] = {
    "MA_TEMP",          # Target leakage into SA_TEMP and contamination of u_hat
    "Magnitude",        # Ground truth injection magnitude
    "Fault Type",       # Ground truth fault label
    "Fault Name",       # Ground truth fault name
    "Duration (h:mm)",  # Ground truth duration
}


def validate_feature_matrix_columns(columns: List[str], target_name: str) -> None:
    """
    Validates that a feature matrix contains no banned channels,
    no unknown channels, and no self-leakage of the target.
    """
    col_set = set(columns)

    # 1. Self-leakage check
    if target_name in col_set:
        raise ValueError(
            f"Target leakage violation: target '{target_name}' is present in feature matrix!"
        )

    # 2. Duplicate / Proxy check (MA_TEMP)
    if "MA_TEMP" in col_set:
        raise ValueError(
            "CSIRO MA_TEMP violation: MA_TEMP identically equals SA_TEMP and cannot be an independent feature."
        )

    # 3. Banned channels check
    banned_present = col_set.intersection(BANNED_CHANNELS)
    if banned_present:
        raise ValueError(
            f"Banned channel violation: feature matrix contains strictly banned channels: {banned_present}"
        )
