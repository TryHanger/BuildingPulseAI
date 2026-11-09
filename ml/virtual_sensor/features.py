from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np

# Canonical Basic feature set for AHU Supply Air Temperature virtual sensor
BASIC_FEATURE_COLUMNS: List[str] = [
    "MA_TEMP",      # Mixed air temperature
    "OA_TEMP",      # Outdoor air temperature
    "RA_TEMP",      # Return air temperature
    "CHWC_VLV_DM",  # Chilled water valve command
    "OA_DMPR_DM",   # Outdoor air damper command
    "SF_SPD_DM",    # Supply fan run status (0/1)
    "SA_TEMPSPT"    # Supply air temperature setpoint
]

TEMPERATURE_COLUMNS: List[str] = [
    "SA_TEMP",
    "MA_TEMP",
    "OA_TEMP",
    "RA_TEMP",
    "SA_TEMPSPT"
]

def fahrenheit_to_celsius(val: float | np.ndarray | pd.Series) -> float | np.ndarray | pd.Series:
    """Converts Fahrenheit to Celsius. Pure deterministic transform: (F - 32) * 5/9."""
    return (val - 32.0) * (5.0 / 9.0)

def celsius_to_fahrenheit(val: float | np.ndarray | pd.Series) -> float | np.ndarray | pd.Series:
    """Converts Celsius to Fahrenheit: C * 9/5 + 32."""
    return (val * 9.0 / 5.0) + 32.0

class FeatureTransformer:
    def __init__(self, feature_cols: Optional[List[str]] = None, target_col: str = "SA_TEMP"):
        self.feature_cols = feature_cols or list(BASIC_FEATURE_COLUMNS)
        self.target_col = target_col
        self.fitted_medians: Dict[str, float] = {}

    def fit(self, df: pd.DataFrame) -> "FeatureTransformer":
        """Calculates imputation medians strictly on training split."""
        df_clean = self._convert_units(df)
        for col in self.feature_cols:
            if col in df_clean.columns:
                med = float(df_clean[col].dropna().median())
                self.fitted_medians[col] = med if not np.isnan(med) else 0.0
            else:
                self.fitted_medians[col] = 0.0
        return self

    def _convert_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """Converts raw temperatures from °F to °C if values are in Fahrenheit range (> 32°F typical)."""
        df_out = df.copy()
        for col in TEMPERATURE_COLUMNS:
            if col in df_out.columns:
                # LBNL temperatures are in °F (around 50°F - 90°F).
                # Check sample mean to ensure no accidental double-conversion
                s_mean = df_out[col].dropna().mean()
                if s_mean > 30.0:  # clearly Fahrenheit
                    df_out[col] = fahrenheit_to_celsius(df_out[col])
        return df_out

    def transform(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[pd.Series], pd.Series]:
        """
        Transforms input DataFrame.
        Returns:
            X: DataFrame with feature_cols in °C/normalized units
            y: Optional Series of target in °C (if target_col present)
            operating_mask: Boolean Series indicating fan is ON (SF_SPD_DM >= 0.5)
        """
        missing_features = [c for c in self.feature_cols if c not in df.columns]
        if missing_features:
            raise ValueError(f"Missing required Basic features in input dataframe: {missing_features}")

        df_c = self._convert_units(df)

        # Operational status: fan running
        if "SF_SPD_DM" in df_c.columns:
            operating_mask = df_c["SF_SPD_DM"] >= 0.5
        else:
            operating_mask = pd.Series(True, index=df_c.index)

        # Impute missing values with fitted medians
        X = pd.DataFrame(index=df_c.index)
        for col in self.feature_cols:
            vals = df_c[col].copy()
            fallback = self.fitted_medians.get(col, 0.0)
            X[col] = vals.fillna(fallback)

        y = None
        if self.target_col in df_c.columns:
            y = df_c[self.target_col].copy()

        return X, y, operating_mask
