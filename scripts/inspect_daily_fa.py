import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS, apply_causal_k_of_n

RAW_DIR = Path('data/raw/rbc_nesbitt')
b3_files = [RAW_DIR / '20160601_Baseline.csv', RAW_DIR / '20160712_Baseline.csv', RAW_DIR / '20170714_Baseline.csv']
val_file = RAW_DIR / '20170729_Baseline.csv'
df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
df_val = load_clean_nesbitt(val_file)
features = ['OA_TEMP', 'RA_TEMP', 'MA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']
m_u = Ridge(alpha=10.0).fit(df_train[features], df_train['CCV_FBK'])
sigma_u = float(np.std(np.abs(df_val['CCV_FBK'].values - m_u.predict(df_val[features])), ddof=1))

for fname, spec in FAULT_SPECS.items():
    df_f = load_clean_nesbitt(RAW_DIR / fname)
    hhmm = df_f['raw_time_hhmm'].values
    is_f_official = (hhmm >= spec['start_hhmm']) & (hhmm <= spec['end_hhmm'])
    
    zu = np.abs(df_f['CCV_FBK'].values - m_u.predict(df_f[features])) / sigma_u
    al_35 = apply_causal_k_of_n(pd.Series(zu), 3.5, 2, 3).values
    al_40 = apply_causal_k_of_n(pd.Series(zu), 4.0, 2, 3).values
    
    norm_35 = al_35[~is_f_official]
    norm_40 = al_40[~is_f_official]
    
    # Check when the false alarms occur (pre-fault vs post-fault)
    pre_fault = hhmm < spec['start_hhmm']
    post_fault = hhmm > spec['end_hhmm']
    
    pre_fa_35 = al_35[pre_fault].sum()
    post_fa_35 = al_35[post_fault].sum()
    
    print(f"=== {fname} ({spec['fault_name']}) ===")
    print(f"Total points: {len(df_f)} | Official Fault points: {is_f_official.sum()} | Official Normal points: {(~is_f_official).sum()}")
    print(f"M2 (tau=3.5): FA total = {norm_35.sum()}/{(~is_f_official).sum()} ({norm_35.mean()*100:.2f}%)")
    print(f"   Pre-fault FA: {pre_fa_35}/{pre_fault.sum()} | Post-fault FA: {post_fa_35}/{post_fault.sum()}")
    if post_fa_35 > 0:
        post_fa_times = hhmm[post_fault & al_35]
        print(f"   Post-fault FA times (hhmm): {post_fa_times}")
    print(f"M2 (tau=4.0): FA total = {norm_40.sum()}/{(~is_f_official).sum()} ({norm_40.mean()*100:.2f}%)")
