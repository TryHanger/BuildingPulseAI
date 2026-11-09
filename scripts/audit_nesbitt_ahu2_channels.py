import os
import pandas as pd
import numpy as np

csv_files = [
    "20160601_Baseline.csv",
    "20160712_Baseline.csv",
    "20170714_Baseline.csv",
    "20170729_Baseline.csv",
    "20170718_OADamStuck_100.csv",
    "20170811_CooCoiValStuck_100.csv",
    "20180710_OADamStuck_30.csv",
    "20180711_CooCoiValStuck_80.csv"
]

print("=== AUDITING RBC-NESBITT AHU2 CHANNELS ===")
raw_dir = "data/raw/rbc_nesbitt"

# AHU2 column indices:
ahu2_map = {
    "OA_TEMP": 2,
    "OA_RH": 3,
    "RA_TEMP": 52,
    "MA_TEMP": 53,
    "SA_TEMP": 54,
    "SF_SPD": 55,
    "ECON_POS": 56,
    "CCV_FBK": 57,
    "ECON_SPT": 58,
    "RF_SPD": 59,
    "BETWEEN_COIL_TEMP": 61,
    "SA_STATIC_PRESS": 62,
    "SA_TEMP_SPT": 63,
    "SA_STATIC_SPT": 64,
    "RA_RH": 65,
    "SA_RH": 68,
    "SF_CURRENT": 69,
    "RF_CURRENT": 70,
    "STEAM_VLV_1_3": 71,
    "STEAM_VLV_2_3": 72,
    "RELIEF_DAMPER": 73,
    "RETURN_DAMPER": 74
}

for fname in csv_files:
    p = os.path.join(raw_dir, fname)
    df = pd.read_csv(p, encoding="latin1")
    print(f"\n--- File: {fname} (rows: {len(df)}) ---")
    
    # Check Time column
    times = df.iloc[:, 1]
    hours = times // 100
    mins = times % 100
    valid_time = ((hours >= 0) & (hours <= 23) & (mins >= 0) & (mins <= 55) & (mins % 5 == 0)).all()
    print(f"Time format valid HHMM 5-min: {valid_time} (min={times.min()}, max={times.max()})")
    
    # Check constant / identical channels
    for name, idx in ahu2_map.items():
        s = df.iloc[:, idx]
        col_name = df.columns[idx]
        is_const = s.nunique() <= 1
        std_val = s.std()
        mean_val = s.mean()
        if is_const:
            print(f"  [CONSTANT] {name:<18s} (col {idx:2d}): value = {mean_val:.2f}")
    
    # Check if MA_TEMP == SA_TEMP
    diff_ma_sa = np.abs(df.iloc[:, 53].values - df.iloc[:, 54].values)
    print(f"  MA vs SA Temp: mean diff = {diff_ma_sa.mean():.2f} °F, max diff = {diff_ma_sa.max():.2f} °F, min diff = {diff_ma_sa.min():.2f} °F")
    
    # Check fan operating rows (SF_SPD > 10% or > 0%)
    sf_spd = df.iloc[:, 55]
    print(f"  SF_SPD distribution: min={sf_spd.min():.1f}%, mean={sf_spd.mean():.1f}%, max={sf_spd.max():.1f}%, pct > 20% = {(sf_spd > 20).mean()*100:.1f}%")
