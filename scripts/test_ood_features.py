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
features = ['OA_TEMP', 'RA_TEMP', 'MA_TEMP', 'SA_TEMP_SPT', 'SF_SPD']
m_u = Ridge(alpha=10.0).fit(df_train[features], df_train['CCV_FBK'])

bounds = {}
for col in features:
    bounds[col] = (df_train[col].min(), df_train[col].max())

print("Training Bounds:")
for k, v in bounds.items():
    print(f"  {k}: [{v[0]:.2f}, {v[1]:.2f}]")

for fname, spec in FAULT_SPECS.items():
    df = load_clean_nesbitt(RAW_DIR / fname)
    is_fault = (df['raw_time_hhmm'] >= spec['start_hhmm']) & (df['raw_time_hhmm'] <= spec['end_hhmm'])
    preds_raw = m_u.predict(df[features])
    preds_clipped = np.clip(preds_raw, 0.0, 100.0)
    
    # Check OOD per feature
    ood_mask = pd.DataFrame(index=df.index)
    for col in features:
        low, high = bounds[col]
        ood_mask[col] = (df[col] < low) | (df[col] > high)
    
    any_ood = ood_mask.any(axis=1)
    
    fault_preds = preds_raw[is_fault]
    neg_count = (fault_preds < 0.0).sum()
    print(f"\n--- {fname} ---")
    print(f"Fault window points: {len(fault_preds)}")
    print(f"Negative predictions in fault window: {neg_count} ({neg_count/len(fault_preds)*100:.1f}%)")
    print(f"Min prediction in fault window: {fault_preds.min():.2f}%")
    print(f"Max prediction in fault window: {fault_preds.max():.2f}%")
    print(f"Fault period OOD points (any feature): {any_ood[is_fault].sum()}/{len(fault_preds)}")
    print("OOD breakdown during fault:")
    for col in features:
        print(f"  {col} OOD: {ood_mask[col][is_fault].sum()}/{len(fault_preds)}")
