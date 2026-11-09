import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS, apply_causal_k_of_n

RAW_DIR = Path('data/raw/rbc_nesbitt')
b3_files = [RAW_DIR / '20160601_Baseline.csv', RAW_DIR / '20160712_Baseline.csv', RAW_DIR / '20170714_Baseline.csv']
val_file = RAW_DIR / '20170729_Baseline.csv'
df_train = pd.concat([load_clean_nesbitt(p) for p in b3_files])
df_val = load_clean_nesbitt(val_file)

f_with_ma = ['OA_TEMP', 'RA_TEMP', 'MA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']
f_no_ma = ['OA_TEMP', 'RA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']

m_u_full = Ridge(alpha=10.0).fit(df_train[f_with_ma], df_train['CCV_FBK'])
m_u_noma = Ridge(alpha=10.0).fit(df_train[f_no_ma], df_train['CCV_FBK'])

sig_full = float(np.std(np.abs(df_val['CCV_FBK'] - m_u_full.predict(df_val[f_with_ma])), ddof=1))
sig_noma = float(np.std(np.abs(df_val['CCV_FBK'] - m_u_noma.predict(df_val[f_no_ma])), ddof=1))

print('M2 Full Coefs:', {k: round(v, 4) for k, v in zip(f_with_ma, m_u_full.coef_)})
print('M2 No MA Coefs:', {k: round(v, 4) for k, v in zip(f_no_ma, m_u_noma.coef_)})
print(f"Train R2: Full={m_u_full.score(df_train[f_with_ma], df_train['CCV_FBK']):.4f}, NoMA={m_u_noma.score(df_train[f_no_ma], df_train['CCV_FBK']):.4f}")
print(f"Val R2: Full={m_u_full.score(df_val[f_with_ma], df_val['CCV_FBK']):.4f}, NoMA={m_u_noma.score(df_val[f_no_ma], df_val['CCV_FBK']):.4f}")
print(f"Sigma_u: Full={sig_full:.4f}, NoMA={sig_noma:.4f}")

# Check negative predictions during 20170718 fault window
df17 = load_clean_nesbitt(RAW_DIR / '20170718_OADamStuck_100.csv')
is_f17 = (df17['raw_time_hhmm'] >= 1100) & (df17['raw_time_hhmm'] <= 2000)
preds_full = m_u_full.predict(df17[is_f17][f_with_ma])
preds_noma = m_u_noma.predict(df17[is_f17][f_no_ma])
print(f"20170718 Fault Preds Full: min={preds_full.min():.2f}%, negative count={(preds_full < 0).sum()}/109")
print(f"20170718 Fault Preds NoMA: min={preds_noma.min():.2f}%, negative count={(preds_noma < 0).sum()}/109")

test_dfs = {fname: load_clean_nesbitt(RAW_DIR / fname) for fname in FAULT_SPECS}
for tau in [3.0, 3.5, 4.0]:
    for name, m, feats, sig in [('M2_FULL', m_u_full, f_with_ma, sig_full), ('M2_NO_MA', m_u_noma, f_no_ma, sig_noma)]:
        det_eps = 0
        norm_fa = []
        for fname, df_t in test_dfs.items():
            spec = FAULT_SPECS[fname]
            is_f = (df_t['raw_time_hhmm'] >= spec['official_start_hhmm']) & (df_t['raw_time_hhmm'] <= spec['official_end_hhmm'])
            pred = m.predict(df_t[feats])
            z = np.abs(df_t['CCV_FBK'] - pred) / sig
            al = apply_causal_k_of_n(pd.Series(z), tau, 2, 3).values
            norm_fa.extend(al[~is_f])
            if np.any(al[is_f]):
                det_eps += 1
        far = np.mean(norm_fa) * 100
        print(f"tau={tau:.2f} | {name:<10s} | Rec: {det_eps}/4 | FAR: {far:.2f}%")
