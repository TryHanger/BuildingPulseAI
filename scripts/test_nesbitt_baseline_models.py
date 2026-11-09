import os
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge

def load_nesbitt_clean(csv_path):
    df = pd.read_csv(csv_path, encoding="latin1")
    # Date and Time
    dates = df.iloc[:, 0].astype(str)
    times = df.iloc[:, 1]
    hours = (times // 100).astype(str).str.zfill(2)
    mins = (times % 100).astype(str).str.zfill(2)
    dt_strings = dates + " " + hours + ":" + mins + ":00"
    dt_index = pd.to_datetime(dt_strings)
    
    # AHU2 channels with conversion to Celsius
    # F to C: (F - 32) * 5/9
    f_to_c = lambda f: (f - 32.0) * (5.0 / 9.0)
    
    df_clean = pd.DataFrame(index=dt_index)
    df_clean["OA_TEMP"] = f_to_c(df.iloc[:, 2].values)
    df_clean["OA_RH"] = df.iloc[:, 3].values
    df_clean["RA_TEMP"] = f_to_c(df.iloc[:, 52].values)
    df_clean["MA_TEMP"] = f_to_c(df.iloc[:, 53].values)
    df_clean["SA_TEMP"] = f_to_c(df.iloc[:, 54].values)
    df_clean["SF_SPD"] = df.iloc[:, 55].values
    df_clean["CCV_FBK"] = df.iloc[:, 57].values # %
    df_clean["SA_TEMP_SPT"] = f_to_c(df.iloc[:, 63].values)
    df_clean["RELIEF_DAMPER"] = df.iloc[:, 73].values
    df_clean["RETURN_DAMPER"] = df.iloc[:, 74].values
    
    # AHU1 channels (for comparison / AHU1 fault)
    df_clean["AHU1_RA_TEMP"] = f_to_c(df.iloc[:, 31].values)
    df_clean["AHU1_MA_TEMP"] = f_to_c(df.iloc[:, 32].values)
    df_clean["AHU1_SA_TEMP"] = f_to_c(df.iloc[:, 33].values)
    df_clean["AHU1_SF_SPD"] = df.iloc[:, 34].values
    df_clean["AHU1_CCV_FBK"] = df.iloc[:, 36].values
    df_clean["AHU1_SA_TEMP_SPT"] = f_to_c(df.iloc[:, 42].values)
    
    df_clean["raw_time_hhmm"] = times.values
    return df_clean

# Test on baselines
df_b1 = load_nesbitt_clean("data/raw/rbc_nesbitt/20170714_Baseline.csv")
df_b2 = load_nesbitt_clean("data/raw/rbc_nesbitt/20170729_Baseline.csv")
print("Baseline 1 (2017-07-14):", df_b1.shape)
print("  OA_TEMP range (°C):", df_b1["OA_TEMP"].min(), "to", df_b1["OA_TEMP"].max())
print("  SA_TEMP range (°C):", df_b1["SA_TEMP"].min(), "to", df_b1["SA_TEMP"].max())
print("  CCV_FBK range (%):", df_b1["CCV_FBK"].min(), "to", df_b1["CCV_FBK"].max())

print("\nBaseline 2 (2017-07-29):", df_b2.shape)
print("  OA_TEMP range (°C):", df_b2["OA_TEMP"].min(), "to", df_b2["OA_TEMP"].max())
print("  SA_TEMP range (°C):", df_b2["SA_TEMP"].min(), "to", df_b2["SA_TEMP"].max())
print("  CCV_FBK range (%):", df_b2["CCV_FBK"].min(), "to", df_b2["CCV_FBK"].max())

# Fit Ridge models on Baseline 1, test on Baseline 2
# 1. Thermal Model (T_ONLY)
features_T = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
m_T = Ridge(alpha=1.0).fit(df_b1[features_T], df_b1["SA_TEMP"])
pred_b1_T = m_T.predict(df_b1[features_T])
pred_b2_T = m_T.predict(df_b2[features_T])
r2_tr_T = 1.0 - np.sum((df_b1["SA_TEMP"] - pred_b1_T)**2) / np.sum((df_b1["SA_TEMP"] - df_b1["SA_TEMP"].mean())**2)
r2_val_T = 1.0 - np.sum((df_b2["SA_TEMP"] - pred_b2_T)**2) / np.sum((df_b2["SA_TEMP"] - df_b2["SA_TEMP"].mean())**2)
mae_tr_T = np.mean(np.abs(df_b1["SA_TEMP"] - pred_b1_T))
mae_val_T = np.mean(np.abs(df_b2["SA_TEMP"] - pred_b2_T))
print(f"\nT_ONLY: Train R2={r2_tr_T:.4f}, Val R2={r2_val_T:.4f}, Train MAE={mae_tr_T:.2f}°C, Val MAE={mae_val_T:.2f}°C")

# 2. Control Effort Model (U_ONLY)
features_u = ["OA_TEMP", "RA_TEMP", "MA_TEMP", "SA_TEMP_SPT", "SF_SPD"]
m_u = Ridge(alpha=10.0).fit(df_b1[features_u], df_b1["CCV_FBK"])
pred_b1_u = m_u.predict(df_b1[features_u])
pred_b2_u = m_u.predict(df_b2[features_u])
r2_tr_u = 1.0 - np.sum((df_b1["CCV_FBK"] - pred_b1_u)**2) / np.sum((df_b1["CCV_FBK"] - df_b1["CCV_FBK"].mean())**2)
r2_val_u = 1.0 - np.sum((df_b2["CCV_FBK"] - pred_b2_u)**2) / np.sum((df_b2["CCV_FBK"] - df_b2["CCV_FBK"].mean())**2)
mae_tr_u = np.mean(np.abs(df_b1["CCV_FBK"] - pred_b1_u))
mae_val_u = np.mean(np.abs(df_b2["CCV_FBK"] - pred_b2_u))
print(f"U_ONLY: Train R2={r2_tr_u:.4f}, Val R2={r2_val_u:.4f}, Train MAE={mae_tr_u:.2f}%, Val MAE={mae_val_u:.2f}%")
