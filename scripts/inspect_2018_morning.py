import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, apply_causal_k_of_n

RAW_DIR = Path('data/raw/rbc_nesbitt')
b3_files = [RAW_DIR / '20160601_Baseline.csv', RAW_DIR / '20160712_Baseline.csv', RAW_DIR / '20170714_Baseline.csv']
val_file = RAW_DIR / '20170729_Baseline.csv'
df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
df_val = load_clean_nesbitt(val_file)
features = ['OA_TEMP', 'RA_TEMP', 'MA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']
m_u = Ridge(alpha=10.0).fit(df_train[features], df_train['CCV_FBK'])
sigma_u = float(np.std(np.abs(df_val['CCV_FBK'].values - m_u.predict(df_val[features])), ddof=1))

df18 = load_clean_nesbitt(RAW_DIR / '20180710_OADamStuck_30.csv')
zu = np.abs(df18['CCV_FBK'].values - m_u.predict(df18[features])) / sigma_u
al = apply_causal_k_of_n(pd.Series(zu), 3.5, 2, 3).values
sub = df18[(df18['raw_time_hhmm'] < 1030) & al]
for idx, r in sub.iterrows():
    loc = df18.index.get_loc(idx)
    pred_val = m_u.predict(r[features].to_frame().T)[0]
    print(f"Time: {int(r['raw_time_hhmm'])} | SF_SPD: {r['SF_SPD']} | OA: {r['OA_TEMP']:.1f} | MA: {r['MA_TEMP']:.1f} | CCV: {r['CCV_FBK']:.1f} | Pred: {pred_val:.1f} | zu: {zu[loc]:.2f}")
