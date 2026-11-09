"""
Temporal split management for CSIRO AHU9 adaptation.
Enforces strict chronological partitioning:
  Train Local:      2013-10-28 to 2013-11-01 (Clean healthy points only, embargo >= 60m)
  Temporal Barrier: 2013-11-02 to 2013-11-03 (Weekend AHU shutdown gap)
  Validation Local: 2013-11-04 to 2013-11-06 (Clean healthy points only, embargo >= 60m)
  Held-Out Test:    2013-11-07 to 2013-11-12 (Uncompromised test block with real faults)
"""

from typing import Dict, Tuple, Optional
import pandas as pd
import numpy as np

class CSIROTemporalSplitter:
    def __init__(
        self,
        train_end: str = "2013-11-01 23:59:59",
        val_start: str = "2013-11-04 00:00:00",
        val_end: str = "2013-11-06 23:59:59",
        test_start: str = "2013-11-07 00:00:00",
        embargo_minutes: int = 60
    ):
        self.train_end = pd.to_datetime(train_end)
        self.val_start = pd.to_datetime(val_start)
        self.val_end = pd.to_datetime(val_end)
        self.test_start = pd.to_datetime(test_start)
        self.embargo_minutes = embargo_minutes

        if self.train_end >= self.val_start:
            raise ValueError(f"Train end ({self.train_end}) must be strictly earlier than Val start ({self.val_start})")
        if self.val_end >= self.test_start:
            raise ValueError(f"Val end ({self.val_end}) must be strictly earlier than Test start ({self.test_start})")

    def build_fault_masks(
        self,
        df: pd.DataFrame,
        df_exp: pd.DataFrame,
        ahu_id: int = 9
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Builds raw fault mask and embargoed fault mask.
        Returns:
            is_fault_raw: bool array, True inside documented fault injection windows
            is_fault_embargo: bool array, True inside fault windows +/- embargo_minutes
        """
        df_ahu = df_exp[df_exp["AHU"] == ahu_id].copy()
        df_ahu["start"] = pd.to_datetime(df_ahu["Start Datetime"])
        df_ahu["end"] = pd.to_datetime(df_ahu["End Datetime"])

        dt_series = pd.to_datetime(df["Datetime"]) if "Datetime" in df.columns else df.index

        is_fault_raw = np.zeros(len(df), dtype=bool)
        is_fault_embargo = np.zeros(len(df), dtype=bool)

        delta = pd.Timedelta(minutes=self.embargo_minutes)
        for _, row in df_ahu.iterrows():
            raw_mask = (dt_series >= row["start"]) & (dt_series <= row["end"])
            emb_mask = (dt_series >= (row["start"] - delta)) & (dt_series <= (row["end"] + delta))
            is_fault_raw |= raw_mask.values if hasattr(raw_mask, "values") else raw_mask
            is_fault_embargo |= emb_mask.values if hasattr(emb_mask, "values") else emb_mask

        return is_fault_raw, is_fault_embargo

    def split(
        self,
        df: pd.DataFrame,
        df_exp: pd.DataFrame
    ) -> Dict[str, Dict[str, any]]:
        """
        Splits dataset into Train, Validation, and Held-Out Test dictionaries.
        """
        dt_series = pd.to_datetime(df["Datetime"]) if "Datetime" in df.columns else df.index

        is_fault_raw, is_fault_embargo = self.build_fault_masks(df, df_exp)
        is_op = (df["SF_SPD_DM"] >= 0.5).values if "SF_SPD_DM" in df.columns else np.ones(len(df), dtype=bool)

        train_idx = np.where(dt_series <= self.train_end)[0]
        val_idx = np.where((dt_series >= self.val_start) & (dt_series <= self.val_end))[0]
        test_idx = np.where(dt_series >= self.test_start)[0]

        # Verify zero overlap
        s_train = set(train_idx)
        s_val = set(val_idx)
        s_test = set(test_idx)
        assert len(s_train.intersection(s_val)) == 0, "Train and Val indices must not overlap!"
        assert len(s_val.intersection(s_test)) == 0, "Val and Test indices must not overlap!"
        assert len(s_train.intersection(s_test)) == 0, "Train and Test indices must not overlap!"

        # Train: operating, clean (no fault, no embargo)
        train_clean_op = train_idx[is_op[train_idx] & ~is_fault_embargo[train_idx]]
        # Val: operating, clean (no fault, no embargo)
        val_clean_op = val_idx[is_op[val_idx] & ~is_fault_embargo[val_idx]]

        # Test: operating normal and operating fault
        test_op = test_idx[is_op[test_idx]]
        test_normal_op = test_idx[is_op[test_idx] & ~is_fault_raw[test_idx]]
        test_fault_op = test_idx[is_op[test_idx] & is_fault_raw[test_idx]]

        return {
            "train": {
                "all_indices": train_idx,
                "clean_operating_indices": train_clean_op,
                "start": str(dt_series[train_idx[0]]),
                "end": str(dt_series[train_idx[-1]])
            },
            "val": {
                "all_indices": val_idx,
                "clean_operating_indices": val_clean_op,
                "start": str(dt_series[val_idx[0]]),
                "end": str(dt_series[val_idx[-1]])
            },
            "test": {
                "all_indices": test_idx,
                "operating_indices": test_op,
                "normal_operating_indices": test_normal_op,
                "fault_operating_indices": test_fault_op,
                "start": str(dt_series[test_idx[0]]),
                "end": str(dt_series[test_idx[-1]])
            },
            "masks": {
                "is_fault_raw": is_fault_raw,
                "is_fault_embargo": is_fault_embargo,
                "is_op": is_op
            }
        }
