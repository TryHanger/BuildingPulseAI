import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS

RAW_DIR = Path('data/raw/rbc_nesbitt')
b3_files = [RAW_DIR / '20160601_Baseline.csv', RAW_DIR / '20160712_Baseline.csv', RAW_DIR / '20170714_Baseline.csv']
val_file = RAW_DIR / '20170729_Baseline.csv'

df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
df_val = load_clean_nesbitt(val_file)

features = ['OA_TEMP', 'RA_TEMP', 'MA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']
m_T = Ridge(alpha=10.0).fit(df_train[features], df_train['SA_TEMP'])

train_r2 = 1.0 - np.sum((df_train['SA_TEMP'] - m_T.predict(df_train[features]))**2) / np.sum((df_train['SA_TEMP'] - df_train['SA_TEMP'].mean())**2)
val_r2 = 1.0 - np.sum((df_val['SA_TEMP'] - m_T.predict(df_val[features]))**2) / np.sum((df_val['SA_TEMP'] - df_val['SA_TEMP'].mean())**2)

print(f"M1 Ridge: Train R2={train_r2:.4f}, Val R2={val_r2:.4f}")
print("M1 Coefs:", dict(zip(features, m_T.coef_)))
print(f"Val SA_TEMP std: {df_val['SA_TEMP'].std():.4f}, MAE: {np.mean(np.abs(df_val['SA_TEMP'] - m_T.predict(df_val[features]))):.4f}")

# What if we use SA_TEMP_SPT directly as a physical thermal baseline (perfect tracking baseline)?
val_track_mae = np.mean(np.abs(df_val['SA_TEMP'] - df_val['SA_TEMP_SPT']))
print(f"Setpoint tracking baseline MAE on Val: {val_track_mae:.4f}")
