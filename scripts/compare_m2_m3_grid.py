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
m_T = Ridge(alpha=10.0).fit(df_train[features], df_train['SA_TEMP'])
m_u = Ridge(alpha=10.0).fit(df_train[features], df_train['CCV_FBK'])

sigma_T = float(np.std(np.abs(df_val['SA_TEMP'].values - m_T.predict(df_val[features])), ddof=1))
sigma_u = float(np.std(np.abs(df_val['CCV_FBK'].values - m_u.predict(df_val[features])), ddof=1))

test_dfs = {fname: load_clean_nesbitt(RAW_DIR / fname) for fname in FAULT_SPECS}

print(f"{'Tau':<5s} | {'M2 Rec(4)':<10s} | {'M2 Rec(3)':<10s} | {'M2 FAR':<8s} | {'M3 Rec(4)':<10s} | {'M3 Rec(3)':<10s} | {'M3 FAR':<8s} | {'Diff FAR (M3-M2)'}")
print("-" * 85)

for tau in [2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.25, 4.5, 5.0]:
    # Evaluate M2
    m2_rec4, m2_rec3 = 0, 0
    m2_norm = []
    # Evaluate M3
    m3_rec4, m3_rec3 = 0, 0
    m3_norm = []
    
    for fname, df_f in test_dfs.items():
        spec = FAULT_SPECS[fname]
        is_f = (df_f['raw_time_hhmm'] >= spec['start_hhmm']) & (df_f['raw_time_hhmm'] <= spec['end_hhmm'])
        is_valid_3 = (spec.get('status') != 'LABEL_OR_SIGNAL_SEMANTICS_UNRESOLVED')
        
        zt = np.abs(df_f['SA_TEMP'].values - m_T.predict(df_f[features])) / sigma_T
        zu = np.abs(df_f['CCV_FBK'].values - m_u.predict(df_f[features])) / sigma_u
        zfus = np.maximum(zt, zu)
        
        al_m2 = apply_causal_k_of_n(pd.Series(zu), tau, 2, 3).values
        al_m3 = apply_causal_k_of_n(pd.Series(zfus), tau, 2, 3).values
        
        m2_norm.extend(al_m2[~is_f])
        m3_norm.extend(al_m3[~is_f])
        
        if np.any(al_m2[is_f]):
            m2_rec4 += 1
            if is_valid_3:
                m2_rec3 += 1
        if np.any(al_m3[is_f]):
            m3_rec4 += 1
            if is_valid_3:
                m3_rec3 += 1
                
    far_m2 = np.mean(m2_norm) * 100
    far_m3 = np.mean(m3_norm) * 100
    diff_far = far_m3 - far_m2
    print(f"{tau:<5.2f} | {m2_rec4}/4       | {m2_rec3}/3       | {far_m2:5.2f}%  | {m3_rec4}/4       | {m3_rec3}/3       | {far_m3:5.2f}%  | +{diff_far:5.2f}%")
