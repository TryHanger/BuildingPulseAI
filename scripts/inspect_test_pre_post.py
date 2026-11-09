import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
from scripts.evaluate_rbc_nesbitt_reconciled import load_clean_nesbitt, FAULT_SPECS

RAW_DIR = Path('data/raw/rbc_nesbitt')

for fname, spec in FAULT_SPECS.items():
    df = load_clean_nesbitt(RAW_DIR / fname)
    fn = spec['fault_name']
    s = spec['start_hhmm']
    e = spec['end_hhmm']
    print(f"=== {fname} ({fn}) ===")
    print(f"Official fault window: {s} to {e}")
    
    pre = df[df['raw_time_hhmm'] < s]
    fault = df[(df['raw_time_hhmm'] >= s) & (df['raw_time_hhmm'] <= e)]
    post = df[df['raw_time_hhmm'] > e]
    
    print(f"Pre-fault SF_SPD range: [{pre['SF_SPD'].min()}, {pre['SF_SPD'].max()}]")
    print(f"Fault SF_SPD range: [{fault['SF_SPD'].min()}, {fault['SF_SPD'].max()}]")
    print(f"Post-fault SF_SPD range: [{post['SF_SPD'].min()}, {post['SF_SPD'].max()}]")
    
    print(f"Damper col 73 pre/fault/post means: {pre['RELIEF_DAMPER'].mean():.1f} / {fault['RELIEF_DAMPER'].mean():.1f} / {post['RELIEF_DAMPER'].mean():.1f}")
    print(f"Damper col 74 pre/fault/post means: {pre['RETURN_DAMPER'].mean():.1f} / {fault['RETURN_DAMPER'].mean():.1f} / {post['RETURN_DAMPER'].mean():.1f}")
    print(f"CCV col 57 pre/fault/post means: {pre['CCV_FBK'].mean():.1f} / {fault['CCV_FBK'].mean():.1f} / {post['CCV_FBK'].mean():.1f}")
