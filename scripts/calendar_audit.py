import sys
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

def audit_ahu_calendar(parquet_path, ahu_name):
    df = pd.read_parquet(parquet_path)
    if "Datetime" in df.columns:
        dt = pd.to_datetime(df["Datetime"])
    elif isinstance(df.index, pd.DatetimeIndex):
        dt = pd.Series(df.index)
    else:
        dt = pd.to_datetime(df.index)

    print(f"=== Calendar & Sampling Audit: {ahu_name} ===")
    print(f"Total rows: {len(df)}")
    print(f"Start: {dt.min()}, End: {dt.max()}")
    
    # Check nulls
    null_counts = df.isnull().sum()
    print(f"Total nulls across all columns: {null_counts.sum()}")
    
    # Check duplicates
    dup_ts = dt.duplicated().sum()
    print(f"Duplicate timestamps: {dup_ts}")
    
    # Delta t distribution
    dt_diff = dt.diff().dropna()
    dt_sec = dt_diff.dt.total_seconds()
    print(f"Delta-t stats (seconds): min={dt_sec.min()}, median={dt_sec.median()}, max={dt_sec.max()}")
    print(f"Delta-t == 30s: {(dt_sec == 30).sum()} ({(dt_sec == 30).mean()*100:.2f}%)")
    print(f"Delta-t == 60s: {(dt_sec == 60).sum()} ({(dt_sec == 60).mean()*100:.2f}%)")
    print(f"Delta-t > 60s (gaps): {(dt_sec > 60).sum()} ({(dt_sec > 60).mean()*100:.2f}%)")
    print(f"Delta-t <= 0s (non-monotonic): {(dt_sec <= 0).sum()}")
    
    # Check specific test slice (2013-10-28 to 2013-11-12)
    mask_slice = (dt >= "2013-10-28") & (dt <= "2013-11-13")
    dt_slice = dt[mask_slice]
    dt_slice_diff = dt_slice.diff().dropna().dt.total_seconds()
    print(f"\nWithin Stage 8 Slice (2013-10-28 to 2013-11-13):")
    print(f"Slice rows: {len(dt_slice)}")
    print(f"Slice gaps (>60s): {(dt_slice_diff > 60).sum()}")
    if (dt_slice_diff > 60).sum() > 0:
        gap_indices = dt_slice.index[1:][dt_slice_diff > 60]
        for g_idx in gap_indices[:10]:
            print(f"   Gap from {dt.loc[g_idx-1]} to {dt.loc[g_idx]} ({(dt.loc[g_idx] - dt.loc[g_idx-1]).total_seconds()/60:.1f} min)")

audit_ahu_calendar("data/raw/csiro_ahu9.parquet", "AHU9 Raw")
audit_ahu_calendar("data/raw/csiro_ahu10.parquet", "AHU10 Raw")
