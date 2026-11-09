import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from ml.control_aware.alarm_policy import apply_causal_k_of_n_filter
from ml.control_aware.events import evaluate_events_and_false_alarms
from ml.control_aware.evaluate_stage8b import split_clean_ahu, extract_physical_fault_episodes, score_physical_episodes
from ml.control_aware.dynamic_features import extract_dynamic_features
from ml.control_aware.dynamic_models import DynamicRidgeControlModel
from ml.adaptation.data import load_csiro_dataset
from ml.control_aware.dataset import load_canonical_csiro_dataframe
from ml.adaptation.splits import CSIROTemporalSplitter

experiments_df = pd.read_parquet("data/raw/csiro_fault_experiments.parquet")
splitter = CSIROTemporalSplitter(embargo_minutes=60)

for ahu_id in [9, 10]:
    print(f"\n=================== AHU-{ahu_id:02d} THRESHOLD SWEEP FOR M4 (U_DYN_EXO) ===================")
    if ahu_id == 9:
        df_raw, _ = load_csiro_dataset("sc_89e2c6028b4f")
    else:
        df_full, _ = load_canonical_csiro_dataframe("data/raw/csiro_ahu10.parquet", ahu_id=10)
        df_raw = df_full.loc["2013-10-28 00:00:00":"2013-11-12 23:59:59"].copy()

    splits = split_clean_ahu(splitter, df_raw, experiments_df, ahu_id=ahu_id)
    df_train = df_raw.iloc[splits["train"]["clean_operating_indices"]].copy()
    df_val = df_raw.iloc[splits["val"]["clean_operating_indices"]].copy()
    df_test = df_raw.iloc[splits["test"]["operating_indices"]].copy()
    dt_test = pd.to_datetime(df_raw["Datetime"].iloc[splits["test"]["operating_indices"]]).values if "Datetime" in df_raw.columns else df_test.index

    X_tr, y_tr = extract_dynamic_features(df_train, include_controller_state=False)
    X_val, y_val = extract_dynamic_features(df_val, include_controller_state=False)
    X_test, y_test = extract_dynamic_features(df_test, include_controller_state=False)

    model = DynamicRidgeControlModel(alpha=10.0).fit(X_tr, y_tr)
    preds_val = model.predict(X_val)
    preds_test = model.predict(X_test)

    sigma_val = float(np.std(np.abs(y_val.values - preds_val), ddof=1))
    z_test = np.abs(y_test.values - preds_test) / sigma_val

    df_phys = extract_physical_fault_episodes(experiments_df, ahu_id, "2013-11-07 00:00:00", "2013-11-12 23:59:00")

    print(f"{'Threshold (tau)':<16} | {'Rows Detected':<15} | {'Phys Detected':<15} | {'FAR (%)':<10} | {'FA Ep/Day':<10} | {'Budget Met?'}")
    print("-" * 80)
    for tau in [3.5, 4.0, 4.5, 4.75, 5.0, 5.25, 5.5, 6.0, 7.0]:
        alarms = apply_causal_k_of_n_filter(pd.Series(z_test, index=dt_test), threshold=tau, k=10, n=15)
        eval_row, _, _ = evaluate_events_and_false_alarms(alarms, experiments_df, ahu_id, "2013-11-07 00:00:00", "2013-11-12 23:59:00", "M4")
        det_p, tot_p, rec_p, _ = score_physical_episodes(alarms, df_phys)
        budget = (eval_row["pointwise_far"] <= 0.05) and (eval_row["false_episodes_per_8h_day"] <= 2.0)
        flag = "PASS <= 5%" if budget else "FAIL (>5%)"
        print(f"tau = {tau:<10.2f} | {eval_row['detected_fault_events']:2d}/36 ({eval_row['event_recall']*100:4.1f}%) | {det_p:2d}/16 ({rec_p*100:4.1f}%) | {eval_row['pointwise_far']*100:6.2f}%   | {eval_row['false_episodes_per_8h_day']:6.2f}     | {flag}")
