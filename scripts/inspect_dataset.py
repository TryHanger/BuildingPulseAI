import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from backend.app.core.canonical_sensors import resolve_canonical_key, CANONICAL_SENSOR_METADATA

def inspect_file(filepath: str):
    p = Path(filepath)
    if not p.exists():
        print(f"[ERROR] File not found: {p}")
        sys.exit(1)

    print(f"==================================================")
    print(f" Inspecting: {p.name}")
    print(f" Size: {p.stat().st_size:,} bytes")
    print(f"==================================================")

    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    elif p.suffix.lower() == ".csv":
        df = pd.read_csv(p, nrows=50000)
    else:
        print(f"[ERROR] Unsupported format: {p.suffix}")
        sys.exit(1)

    print(f"Shape: {df.shape[0]} rows (sampled/read) x {df.shape[1]} columns")

    # Time column detection
    time_col = None
    for cand in ["Datetime", "datetime", "timestamp", "Time", "time"]:
        if cand in df.columns:
            time_col = cand
            break

    if time_col:
        print(f"[OK] Time column: '{time_col}'")
        t_start = df[time_col].iloc[0]
        t_end = df[time_col].iloc[-1]
        print(f"     Range: {t_start} -> {t_end}")
        t_series = pd.to_datetime(df[time_col], errors="coerce")
        print(f"     Monotonic: {t_series.is_monotonic_increasing}")
        print(f"     Duplicates: {t_series.duplicated().sum()}")
    else:
        print(f"[WARN] No standard time column found! First column is: '{df.columns[0]}'")

    print("\n--- Channels & Mapping ---")
    canonical_count = 0
    for col in df.columns:
        if col == time_col:
            continue
        c_key = resolve_canonical_key(col)
        null_count = df[col].isnull().sum()
        dtype = str(df[col].dtype)
        if c_key:
            canonical_count += 1
            meta = CANONICAL_SENSOR_METADATA[c_key]
            basic_str = "BASIC" if meta["is_basic"] else "EXTENDED"
            print(f"  + {col:<20} -> {c_key:<15} [{meta['component']:<12}] [{basic_str}] nulls: {null_count}")
        else:
            print(f"  ? {col:<20} -> UNKNOWN [CUSTOM] nulls: {null_count}")

    print(f"\nCanonical recognized: {canonical_count} / {len(df.columns) - (1 if time_col else 0)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI утилита для быстрой инспекции CSV/Parquet датасетов AHU")
    parser.add_argument("path", type=str, help="Путь к файлу .csv или .parquet")
    args = parser.parse_args()
    inspect_file(args.path)
