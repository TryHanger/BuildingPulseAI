import hashlib
from typing import Tuple, Dict, Any, List
import pandas as pd

class BlockTemporalSplit:
    """
    Strict block-based chronological split for time-series without shuffle leakage.
    Train: Days 1-9 (12,960 minutes)
    Validation: Days 10-11 (2,880 minutes) - used strictly for threshold calibration and validation metrics
    Held-out Normal Test: Days 12-14 (4,320 minutes) - used strictly for unbiased evaluation
    """
    def __init__(self, train_days: int = 9, val_days: int = 2):
        self.train_points = train_days * 1440
        self.val_points = val_days * 1440

    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        n = len(df)
        if n < self.train_points + self.val_points:
            raise ValueError(
                f"DataFrame has {n} rows, required at least {self.train_points + self.val_points} for train+val blocks"
            )

        train_end = self.train_points
        val_end = self.train_points + self.val_points

        df_train = df.iloc[:train_end].copy()
        df_val = df.iloc[train_end:val_end].copy()
        df_test = df.iloc[val_end:].copy()

        return df_train, df_val, df_test

    def get_split_hash(self) -> str:
        s = f"block_split_v1:train={self.train_points}:val={self.val_points}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


class MultiSeasonTemporalSplit:
    """
    Multi-season temporal split for annual AHU data (Chicago TMY).
    Extracts 4 distinct 14-day seasonal windows without shuffle leakage:
      - Winter: Days 1-14 (Jan 1 - Jan 15)
      - Spring: Days 105-118 (Apr 15 - Apr 29)
      - Summer: Days 196-209 (Jul 15 - Jul 29)
      - Autumn: Days 283-296 (Oct 10 - Oct 24)
    Within each season:
      - Train: First 9 days (12,960 min)
      - Val: Next 2 days (2,880 min)
      - Test: Last 3 days (4,320 min)
    """
    SEASONS: Dict[str, Tuple[int, int]] = {
        "winter": (0, 14 * 1440),
        "spring": (104 * 1440, (104 + 14) * 1440),
        "summer": (195 * 1440, (195 + 14) * 1440),
        "autumn": (282 * 1440, (282 + 14) * 1440)
    }

    def __init__(self, train_days: int = 9, val_days: int = 2):
        self.train_points_per_season = train_days * 1440
        self.val_points_per_season = val_days * 1440
        self.test_points_per_season = (14 - train_days - val_days) * 1440

    def split_annual(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Splits annual dataframe into combined multi-season train, val, held-out test,
        and returns a dictionary of seasonal held-out test splits.
        """
        n = len(df)
        if n < 300 * 1440:  # Need at least up to autumn (~296 days = 426,240 min)
            # If not full annual, fallback to single block split
            splitter = BlockTemporalSplit()
            tr, v, te = splitter.split(df)
            return tr, v, te, {"winter": te}

        train_chunks = []
        val_chunks = []
        test_chunks = []
        season_tests = {}

        for season_name, (start_idx, end_idx) in self.SEASONS.items():
            season_df = df.iloc[start_idx:end_idx].copy()
            tr_end = self.train_points_per_season
            v_end = tr_end + self.val_points_per_season

            s_tr = season_df.iloc[:tr_end]
            s_val = season_df.iloc[tr_end:v_end]
            s_te = season_df.iloc[v_end:]

            train_chunks.append(s_tr)
            val_chunks.append(s_val)
            test_chunks.append(s_te)
            season_tests[season_name] = s_te

        df_train = pd.concat(train_chunks, ignore_index=True)
        df_val = pd.concat(val_chunks, ignore_index=True)
        df_test = pd.concat(test_chunks, ignore_index=True)

        return df_train, df_val, df_test, season_tests

    def get_split_hash(self) -> str:
        s = f"multiseason_split_v2:seasons=4:tr={self.train_points_per_season}:val={self.val_points_per_season}"
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
