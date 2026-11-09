import sys
sys.path.insert(0, ".")
from ml.control_aware.evaluate_stage8b import split_clean_ahu, extract_physical_fault_episodes, score_physical_episodes
from ml.control_aware.dynamic_features import extract_dynamic_features
from ml.control_aware.dynamic_models import DynamicRidgeControlModel
from ml.adaptation.data import load_csiro_dataset
from ml.control_aware.dataset import load_canonical_csiro_dataframe
from ml.adaptation.splits import CSIROTemporalSplitter
from ml.control_aware.alarm_policy import apply_causal_k_of_n_filter
from ml.control_aware.events import evaluate_events_and_false_alarms
import pandas as pd
import numpy as np

df_exp = pd.read_parquet("data/raw/csiro_fault_experiments.parquet")
splitter = CSIROTemporalSplitter(embargo_minutes=60)

for ahu_id in [9, 10]:
    print(f"\n=================== AHU-{ahu_id:02d} M4 vs M5 MATCHED-FAR COMPARISON ===================")
    if ahu_id == 9:
        df_raw, _ = load_csiro_dataset("sc_89e2c6028b4f")
    else:
        df_full, _ = load_canonical_csiro_dataframe("data/raw/csiro_ahu10.parquet", ahu_id=10)
        df_raw = df_full.loc["2013-10-28 00:00:00":"2013-11-12 23:59:59"].copy()

    splits = split_clean_ahu(splitter, df_raw, df_exp, ahu_id=ahu_id)
    df_train = df_raw.iloc[splits["train"]["clean_operating_indices"]].copy()
    df_val = df_raw.iloc[splits["val"]["clean_operating_indices"]].copy()
    df_test = df_raw.iloc[splits["test"]["operating_indices"]].copy()
    dt_test = pd.to_datetime(df_raw["Datetime"].iloc[splits["test"]["operating_indices"]]).values if "Datetime" in df_raw.columns else df_test.index

    # M4 Exo
    X_tr_m4, y_tr_m4 = extract_dynamic_features(df_train, False)
    X_val_m4, y_val_m4 = extract_dynamic_features(df_val, False)
    X_test_m4, y_test_m4 = extract_dynamic_features(df_test, False)
    m4 = DynamicRidgeControlModel(alpha=10.0).fit(X_tr_m4, y_tr_m4)
    sig_m4 = float(np.std(np.abs(y_val_m4.values - m4.predict(X_val_m4)), ddof=1))
    z_m4 = np.abs(y_test_m4.values - m4.predict(X_test_m4)) / sig_m4

    # M5 Ctrl
    X_tr_m5, y_tr_m5 = extract_dynamic_features(df_train, True)
    X_val_m5, y_val_m5 = extract_dynamic_features(df_val, True)
    X_test_m5, y_test_m5 = extract_dynamic_features(df_test, True)
    m5 = DynamicRidgeControlModel(alpha=10.0).fit(X_tr_m5, y_tr_m5)
    sig_m5 = float(np.std(np.abs(y_val_m5.values - m5.predict(X_val_m5)), ddof=1))
    z_m5 = np.abs(y_test_m5.values - m5.predict(X_test_m5)) / sig_m5

    df_phys = extract_physical_fault_episodes(df_exp, ahu_id, "2013-11-07 00:00:00", "2013-11-12 23:59:00")

    print(f"{'Model':<8} | {'Tau':<5} | {'Rows Detected':<15} | {'Phys Detected':<15} | {'FAR (%)':<8} | {'FA Ep/Day':<10}")
    print("-" * 75)
    for name, z_arr in [("M4_EXO", z_m4), ("M5_CTRL", z_m5)]:
        for tau in [3.0, 3.5, 4.0, 4.5, 4.75, 5.0, 5.5, 6.0]:
            al = apply_causal_k_of_n_filter(pd.Series(z_arr, index=dt_test), threshold=tau, k=10, n=15)
            ev, _, _ = evaluate_events_and_false_alarms(al, df_exp, ahu_id, "2013-11-07 00:00:00", "2013-11-12 23:59:00", name)
            dp, tp, rp, _ = score_physical_episodes(al, df_phys)
            print(f"{name:<8} | {tau:<5.2f} | {ev['detected_fault_events']:2d}/36 ({ev['event_recall']*100:4.1f}%) | {dp:2d}/16 ({rp*100:4.1f}%) | {ev['pointwise_far']*100:5.2f}% | {ev['false_episodes_per_8h_day']:5.2f}")
