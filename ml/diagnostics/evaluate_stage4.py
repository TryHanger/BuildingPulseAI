import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.metrics import classification_report, confusion_matrix, f1_score
import lightgbm as lgb
import joblib

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
from ml.virtual_sensor.dataset import load_scenario_data
from ml.diagnostics.sensor_profiles import (
    SensorProfileRegistry,
    extract_profile_diagnostic_features
)
from ml.diagnostics.rules import RuleDiagnosticEngine
from ml.diagnostics.classifier import TARGET_CLASSES
from ml.diagnostics.evidence import EvidenceEvaluator
from ml.diagnostics.confidence_baselines import ConfidenceOnlyBaseline, MarginEntropyBaseline
from ml.diagnostics.decision_layer import EvidenceAwareDecisionLayer
from ml.diagnostics.metrics_selective import (
    compute_selective_risk_at_threshold,
    compute_risk_coverage_curve,
    compute_set_metrics,
    compute_end_to_end_metrics
)

# Standardized Scenario-Level Split
TRAIN_SCENARIOS = [
    {"scenario_id": "sc_3556175a5da2", "class": "FAULT_FREE", "name": "AHU_annual (Normal Train Days 1-9)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_835609dfd906", "class": "SENSOR_BIAS_SA", "name": "coi_bias_-4_annual.csv (-4°C)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_90decfb04993", "class": "SENSOR_BIAS_SA", "name": "coi_bias_4_annual.csv (+4°C)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_276968373895", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_025_annual.csv (25%)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_4ca7822e8e04", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_075_annual.csv (75%)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_1e3ca900a8d7", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_025_annual.csv (25%)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_48ae2acfcea2", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_100_annual_short.csv (100%)", "slice": (0, 9*1440)}
]

TEST_SCENARIOS = [
    {"scenario_id": "sc_3556175a5da2", "class": "FAULT_FREE", "name": "AHU_annual (Held-out Test Days 12-14)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_4c635ed85f83", "class": "SENSOR_BIAS_SA", "name": "coi_bias_-2_annual.csv (-2°C)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_22370df7e61a", "class": "SENSOR_BIAS_SA", "name": "coi_bias_2_annual.csv (+2°C)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_2541462c0f4a", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_010_annual.csv (10%)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_413e7074ae9e", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_050_annual.csv (50%)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_a04b8cceeebc", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_010_annual.csv (10%)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_ef6581a6ce7b", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_075_annual.csv (75%)", "slice": (11*1440, 14*1440)}
]

def prepare_profile_data(
    scenarios_list: List[Dict[str, Any]],
    profile_id: str,
    engine: VirtualSensorInferenceEngine,
    vs_model_id: str = "vs-sa-temp-v2"
) -> Tuple[pd.DataFrame, pd.Series, List[pd.DataFrame], List[np.ndarray], List[pd.Series]]:
    vs_model, vs_trans, _ = engine.load_model(vs_model_id)

    X_list = []
    y_list = []
    raw_dfs = []
    vs_preds = []
    op_masks = []

    for sc in scenarios_list:
        df, _ = load_scenario_data(sc["scenario_id"])
        s_start, s_end = sc["slice"]
        df_slice = df.iloc[s_start:s_end].copy().reset_index(drop=True)

        X_vs, _, op_mask = vs_trans.transform(df_slice)
        pred = vs_model.predict(X_vs)

        # Profile feature extraction
        X_feats, _ = extract_profile_diagnostic_features(df_slice, pred, profile_id=profile_id)

        valid_idx = op_mask & df_slice["SA_TEMP"].notna()
        X_op = X_feats[valid_idx].copy()
        y_op = pd.Series(sc["class"], index=X_op.index)

        X_list.append(X_op)
        y_list.append(y_op)

        raw_dfs.append(df_slice)
        vs_preds.append(pred)
        op_masks.append(op_mask)

    X_all = pd.concat(X_list, ignore_index=True)
    y_all = pd.concat(y_list, ignore_index=True)
    return X_all, y_all, raw_dfs, vs_preds, op_masks

def train_profile_classifier(
    X_train: pd.DataFrame,
    y_train: pd.Series
) -> Tuple[lgb.LGBMClassifier, List[str]]:
    feature_names = list(X_train.columns)
    clf = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=len(TARGET_CLASSES),
        learning_rate=0.05,
        max_depth=4,
        num_leaves=15,
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
        verbose=-1
    )
    clf.fit(X_train[feature_names], y_train)
    return clf, feature_names

def run_stage4_experiments():
    print("==================================================================")
    print(" BUILDINGPULSE AI — STAGE 4 SCIENTIFIC EXPERIMENTS (E4.1 & E4.2) ")
    print("==================================================================\n")

    engine = VirtualSensorInferenceEngine()
    figures_dir = Path("research/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = Path("research/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # PART 1: Observability Profiles Models Training & Eval (E4.2)
    # ---------------------------------------------------------
    profiles = ["BASIC", "BASIC_PLUS_VALVE", "BASIC_PLUS_DAMPER", "BASIC_PLUS_BOTH", "FULL"]
    profile_results = {}
    profile_models = {}

    print("--- STEP 1: Training and Evaluating Observability Profiles (E4.2) ---")
    for pid in profiles:
        print(f"\nProcessing Profile: {pid}")
        X_tr, y_tr, _, _, _ = prepare_profile_data(TRAIN_SCENARIOS, pid, engine)
        X_te, y_te, te_dfs, te_preds, te_ops = prepare_profile_data(TEST_SCENARIOS, pid, engine)

        clf, feat_names = train_profile_classifier(X_tr, y_tr)
        profile_models[pid] = (clf, feat_names)

        # Save profile model
        model_save_path = f"models/classifier_{pid.lower()}.joblib"
        joblib.dump({"model": clf, "features": feat_names, "classes": TARGET_CLASSES}, model_save_path)

        y_pred = clf.predict(X_te[feat_names])
        macro_f1 = float(f1_score(y_te, y_pred, average="macro", zero_division=0))
        cm = confusion_matrix(y_te, y_pred, labels=TARGET_CLASSES)
        report = classification_report(y_te, y_pred, labels=TARGET_CLASSES, output_dict=True, zero_division=0)

        profile_results[pid] = {
            "macro_f1": round(macro_f1, 4),
            "feature_count": len(feat_names),
            "features": feat_names,
            "confusion_matrix": cm.tolist(),
            "per_class": {
                c: {
                    "precision": round(report[c]["precision"], 4),
                    "recall": round(report[c]["recall"], 4),
                    "f1": round(report[c]["f1-score"], 4),
                    "support": int(report[c]["support"])
                }
                for c in TARGET_CLASSES if c in report
            }
        }
        print(f"  {pid}: Features={len(feat_names)}, Macro F1 = {macro_f1:.4f}")
        for c in TARGET_CLASSES:
            if c in report:
                print(f"    {c:22s} F1: {report[c]['f1-score']:.4f}")

    # ---------------------------------------------------------
    # PART 2: Window-Level Decision Layer & Baselines Evaluation (E4.1)
    # ---------------------------------------------------------
    print("\n--- STEP 2: Window-Level Evaluation on BASIC Profile (E4.1) ---")
    clf_basic, feats_basic = profile_models["BASIC"]
    clf_valve, feats_valve = profile_models["BASIC_PLUS_VALVE"]

    # Evaluate on held-out test in 15-minute diagnostic windows
    window_results = []
    window_size = 15
    residual_threshold = 0.919

    decision_layer = EvidenceAwareDecisionLayer()
    b1_engine = ConfidenceOnlyBaseline(tau=0.50)
    b2_engine = MarginEntropyBaseline(margin_delta=0.30, max_entropy=0.85)
    rule_engine = RuleDiagnosticEngine(residual_threshold=residual_threshold)

    for sc_idx, sc_info in enumerate(TEST_SCENARIOS):
        df_raw = te_dfs[sc_idx]
        pred_vs = te_preds[sc_idx]
        op_mask = te_ops[sc_idx]
        true_cls = sc_info["class"]

        n_windows = len(df_raw) // window_size
        for w_i in range(n_windows):
            start_i = w_i * window_size
            end_i = start_i + window_size
            df_w = df_raw.iloc[start_i:end_i].copy()
            pred_w = pred_vs[start_i:end_i]
            op_w = op_mask.iloc[start_i:end_i]

            # Operating ratio in window
            op_ratio = op_w.mean()
            if op_ratio < 0.8:
                continue  # Skip AHU_OFF / transient windows

            # 1. Anomaly Detection
            valid_m = op_w.values & df_w["SA_TEMP"].notna().values
            mean_abs_res = float(np.mean(np.abs(df_w["SA_TEMP"].values[valid_m] - pred_w[valid_m]))) if np.any(valid_m) else 0.0
            anomaly_detected = (mean_abs_res >= residual_threshold)

            # 2. Extract Basic features & Classifier probs
            f_w_basic, _ = extract_profile_diagnostic_features(df_w, pred_w, profile_id="BASIC")
            f_w_mean_basic = f_w_basic[feats_basic].mean(axis=0).to_frame().T
            probs_arr = clf_basic.predict_proba(f_w_mean_basic)[0]
            class_probs = {c: float(probs_arr[i]) for i, c in enumerate(clf_basic.classes_)}

            # 3. Evidence Evaluator for BASIC
            allowed_basic = set(SensorProfileRegistry.get_allowed_channels("BASIC"))
            evaluator_basic = EvidenceEvaluator(allowed_basic)
            ev_list_basic = evaluator_basic.evaluate_window_evidence(
                df_w, pred_w, residual_threshold, op_w.values
            )

            # 4. Evidence Evaluator for BASIC_PLUS_VALVE (to compare)
            allowed_valve = set(SensorProfileRegistry.get_allowed_channels("BASIC_PLUS_VALVE"))
            evaluator_valve = EvidenceEvaluator(allowed_valve)
            ev_list_valve = evaluator_valve.evaluate_window_evidence(
                df_w, pred_w, residual_threshold, op_w.values
            )
            f_w_valve, _ = extract_profile_diagnostic_features(df_w, pred_w, profile_id="BASIC_PLUS_VALVE")
            f_w_mean_valve = f_w_valve[feats_valve].mean(axis=0).to_frame().T
            probs_arr_valve = clf_valve.predict_proba(f_w_mean_valve)[0]
            class_probs_valve = {c: float(probs_arr_valve[i]) for i, c in enumerate(clf_valve.classes_)}

            # 5. Method M (Decision Layer) on BASIC
            res_M = decision_layer.evaluate(
                domain_status="VALIDATED",
                is_operating=True,
                anomaly_detected=anomaly_detected,
                classifier_probs=class_probs,
                evidence_list=ev_list_basic,
                profile_id="BASIC"
            )

            # 6. Method M on BASIC_PLUS_VALVE
            res_M_valve = decision_layer.evaluate(
                domain_status="VALIDATED",
                is_operating=True,
                anomaly_detected=anomaly_detected,
                classifier_probs=class_probs_valve,
                evidence_list=ev_list_valve,
                profile_id="BASIC_PLUS_VALVE"
            )

            # 7. Baseline B1 (Confidence-only)
            res_B1 = b1_engine.predict_window(class_probs) if anomaly_detected else {"status": "NO_ANOMALY", "single_cause": None}

            # 8. Baseline B2 (Margin/Entropy)
            res_B2 = b2_engine.predict_window(class_probs) if anomaly_detected else {"status": "NO_ANOMALY", "single_cause": None}

            # 9. Baseline B0 (Rules)
            rule_pred = rule_engine.predict(f_w_mean_basic)[0]

            window_results.append({
                "scenario_id": sc_info["scenario_id"],
                "true_class": true_cls,
                "anomaly_detected": anomaly_detected,
                "mean_abs_residual": round(mean_abs_res, 3),
                "probs_basic": class_probs,
                "probs_valve": class_probs_valve,
                "B0_pred": rule_pred,
                "B1": res_B1,
                "B2": res_B2,
                "M_basic": res_M,
                "M_valve": res_M_valve
            })

    # ---------------------------------------------------------
    # PART 3: Compute Selective Risk-Coverage Curves (E4.1 - Fair Same-Profile Comparison)
    # ---------------------------------------------------------
    # Subset D: Ground Truth Fault instances where anomaly was detected
    detected_fault_windows = [w for w in window_results if w["true_class"] != "FAULT_FREE" and w["anomaly_detected"]]
    total_fault_windows = [w for w in window_results if w["true_class"] != "FAULT_FREE"]
    normal_windows = [w for w in window_results if w["true_class"] == "FAULT_FREE"]

    print(f"\nEvaluated Windows (Dependent Minute Windows from N={len(TEST_SCENARIOS)} Independent Test Scenarios):")
    print(f"  Total eligible fault windows |F|: {len(total_fault_windows)}")
    print(f"  Detected fault windows |D|:       {len(detected_fault_windows)} (Detection Recall = {len(detected_fault_windows)/len(total_fault_windows):.2%})")
    print(f"  Normal windows evaluated:         {len(normal_windows)}")
    false_alarms = [w for w in normal_windows if w["anomaly_detected"]]
    print(f"  Normal false alarms:              {len(false_alarms)} ({len(false_alarms)/len(normal_windows):.2%})")

    y_true_D = [w["true_class"] for w in detected_fault_windows]

    # --- H1 FAIR COMPARISON 1: ON BASIC PROFILE (B1_basic, B2_basic, M_basic) ---
    tau_grid = np.linspace(0.30, 0.95, 20)
    delta_grid = np.linspace(0.05, 0.65, 20)

    # B1 on Basic
    b1_basic_preds = [max(w["probs_basic"].items(), key=lambda x: x[1])[0] for w in detected_fault_windows]
    b1_basic_scores = [max(w["probs_basic"].values()) for w in detected_fault_windows]
    b1_curve_basic = compute_risk_coverage_curve(y_true_D, b1_basic_preds, b1_basic_scores, tau_grid)

    # B2 on Basic
    b2_basic_scores = []
    b2_basic_preds = []
    for w in detected_fault_windows:
        sp = sorted(w["probs_basic"].items(), key=lambda x: x[1], reverse=True)
        m = sp[0][1] - (sp[1][1] if len(sp) > 1 else 0.0)
        b2_basic_scores.append(m)
        b2_basic_preds.append(sp[0][0])
    b2_curve_basic = compute_risk_coverage_curve(y_true_D, b2_basic_preds, b2_basic_scores, delta_grid)

    # M (Decision Layer) on Basic
    m_single_mask_basic = [w["M_basic"]["status"] == "SINGLE_CAUSE" for w in detected_fault_windows]
    m_preds_basic = [w["M_basic"]["single_cause"] if w["M_basic"]["single_cause"] else "NONE" for w in detected_fault_windows]
    m_scores_basic = [max(w["probs_basic"].values()) for w in detected_fault_windows]
    m_curve_basic = compute_risk_coverage_curve(y_true_D, m_preds_basic, m_scores_basic, tau_grid, is_singleton=m_single_mask_basic)

    # --- H1 FAIR COMPARISON 2: ON BASIC_PLUS_VALVE PROFILE (B1_valve, B2_valve, M_valve) ---
    # Baseline B1 on Valve
    b1_valve_preds = [max(w["probs_valve"].items(), key=lambda x: x[1])[0] for w in detected_fault_windows] if "probs_valve" in detected_fault_windows[0] else []
    b1_valve_scores = [max(w["probs_valve"].values()) for w in detected_fault_windows] if "probs_valve" in detected_fault_windows[0] else []
    b1_curve_valve = compute_risk_coverage_curve(y_true_D, b1_valve_preds, b1_valve_scores, tau_grid) if b1_valve_preds else []

    # Baseline B2 on Valve
    b2_valve_scores = []
    b2_valve_preds = []
    for w in detected_fault_windows:
        pv = w.get("probs_valve", w["probs_basic"])
        sp = sorted(pv.items(), key=lambda x: x[1], reverse=True)
        m = sp[0][1] - (sp[1][1] if len(sp) > 1 else 0.0)
        b2_valve_scores.append(m)
        b2_valve_preds.append(sp[0][0])
    b2_curve_valve = compute_risk_coverage_curve(y_true_D, b2_valve_preds, b2_valve_scores, delta_grid)

    # Decision Layer M on Valve
    m_valve_single_mask = [w["M_valve"]["status"] == "SINGLE_CAUSE" for w in detected_fault_windows]
    m_valve_preds = [w["M_valve"]["single_cause"] if w["M_valve"]["single_cause"] else "NONE" for w in detected_fault_windows]
    m_valve_scores = [max(w.get("probs_valve", w["probs_basic"]).values()) for w in detected_fault_windows]
    m_valve_curve = compute_risk_coverage_curve(y_true_D, m_valve_preds, m_valve_scores, tau_grid, is_singleton=m_valve_single_mask)

    # Fixed points comparison helper
    def find_nearest_cov(curve, target_cov):
        valid = [pt for pt in curve if pt["coverage"] > 0 and pt["risk"] is not None]
        if not valid:
            return None
        return min(valid, key=lambda x: abs(x["coverage"] - target_cov))

    print("\n--- H1 FAIR COMPARISON: ON SAME BASIC PROFILE ---")
    print("| Target Coverage | B1 (Confidence) Risk | B2 (Margin) Risk | Decision Layer M (BASIC) Risk |")
    print("| :---: | :---: | :---: | :---: |")
    for t_cov in [0.40, 0.60, 0.80]:
        p_b1 = find_nearest_cov(b1_curve_basic, t_cov)
        p_b2 = find_nearest_cov(b2_curve_basic, t_cov)
        p_m = find_nearest_cov(m_curve_basic, t_cov)

        r_b1 = f"{p_b1['risk']:.3f} (cov={p_b1['coverage']:.2f})" if p_b1 else "N/A"
        r_b2 = f"{p_b2['risk']:.3f} (cov={p_b2['coverage']:.2f})" if p_b2 else "N/A"
        r_m = f"{p_m['risk']:.3f} (cov={p_m['coverage']:.2f})" if p_m else "N/A"
        print(f"| {t_cov:.2f} | {r_b1} | {r_b2} | {r_m} |")

    print("\n--- H1 FAIR COMPARISON: ON SAME BASIC_PLUS_VALVE PROFILE ---")
    print("| Target Coverage | B1 (Confidence) Risk | B2 (Margin) Risk | Decision Layer M (+VALVE) Risk |")
    print("| :---: | :---: | :---: | :---: |")
    for t_cov in [0.40, 0.60, 0.80]:
        p_b1v = find_nearest_cov(b1_curve_valve, t_cov)
        p_b2v = find_nearest_cov(b2_curve_valve, t_cov)
        p_mv = find_nearest_cov(m_valve_curve, t_cov)

        r_b1v = f"{p_b1v['risk']:.3f} (cov={p_b1v['coverage']:.2f})" if p_b1v else "N/A"
        r_b2v = f"{p_b2v['risk']:.3f} (cov={p_b2v['coverage']:.2f})" if p_b2v else "N/A"
        r_mv = f"{p_mv['risk']:.3f} (cov={p_mv['coverage']:.2f})" if p_mv else "N/A"
        print(f"| {t_cov:.2f} | {r_b1v} | {r_b2v} | {r_mv} |")

    # Set Metrics for M (BASIC) and M (+VALVE)
    candidate_sets_m_basic = [w["M_basic"]["candidate_causes"] for w in detected_fault_windows]
    set_metrics_m_basic = compute_set_metrics(y_true_D, candidate_sets_m_basic)

    candidate_sets_m_valve = [w["M_valve"]["candidate_causes"] for w in detected_fault_windows]
    set_metrics_m_valve = compute_set_metrics(y_true_D, candidate_sets_m_valve)

    print("\nCandidate Set Quality on Detected Faults |D|:")
    print(f"  Decision Layer (BASIC):")
    print(f"    Set Coverage (Ground truth in set): {set_metrics_m_basic['set_coverage']:.2%}")
    print(f"    Mean Set Size:                      {set_metrics_m_basic['mean_set_size']:.2f}")
    print(f"    Singleton Rate (Decisive):          {set_metrics_m_basic['singleton_rate']:.2%}")
    print(f"    Multi-Cause Rate (Ambiguous):       {set_metrics_m_basic['multi_cause_rate']:.2%}")
    print(f"    Unresolved Rate:                    {set_metrics_m_basic['unresolved_rate']:.2%}")

    print(f"  Decision Layer (BASIC_PLUS_VALVE):")
    print(f"    Set Coverage (Ground truth in set): {set_metrics_m_valve['set_coverage']:.2%}")
    print(f"    Mean Set Size:                      {set_metrics_m_valve['mean_set_size']:.2f}")
    print(f"    Singleton Rate (Decisive):          {set_metrics_m_valve['singleton_rate']:.2%}")
    print(f"    Multi-Cause Rate (Ambiguous):       {set_metrics_m_valve['multi_cause_rate']:.2%}")
    print(f"    Unresolved Rate:                    {set_metrics_m_valve['unresolved_rate']:.2%}")

    # ---------------------------------------------------------
    # PART 4: Generate Publication Figures
    # ---------------------------------------------------------
    print("\n--- STEP 3: Generating Figures in research/figures/ ---")
    # Figure 1: Risk-Coverage Curve Comparison (Fair same-profile comparison)
    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot([p["coverage"] for p in b1_curve_basic if p["risk"] is not None],
             [p["risk"] for p in b1_curve_basic if p["risk"] is not None],
             marker="o", label="B1: Confidence-Only (Basic Profile)", color="#3b82f6", linewidth=1.8, linestyle="--")
    plt.plot([p["coverage"] for p in b2_curve_basic if p["risk"] is not None],
             [p["risk"] for p in b2_curve_basic if p["risk"] is not None],
             marker="s", label="B2: Margin/Entropy (Basic Profile)", color="#f59e0b", linewidth=1.8, linestyle="--")
    plt.plot([p["coverage"] for p in m_curve_basic if p["risk"] is not None],
             [p["risk"] for p in m_curve_basic if p["risk"] is not None],
             marker="^", label="M: Decision Layer (Basic Profile)", color="#10b981", linewidth=2.5)

    if b1_curve_valve:
        plt.plot([p["coverage"] for p in b1_curve_valve if p["risk"] is not None],
                 [p["risk"] for p in b1_curve_valve if p["risk"] is not None],
                 marker=".", label="B1: Confidence-Only (+Valve Profile)", color="#6366f1", linewidth=1.5, linestyle=":")
    plt.plot([p["coverage"] for p in m_valve_curve if p["risk"] is not None],
             [p["risk"] for p in m_valve_curve if p["risk"] is not None],
             marker="D", label="M: Decision Layer (+Valve Profile)", color="#8b5cf6", linewidth=2.5)

    plt.xlabel("Selective Coverage (|Accepted Singletons| / |Detected Faults|)", fontsize=11)
    plt.ylabel("Selective Risk (Error Rate in Accepted Singletons)", fontsize=11)
    plt.title("BuildingPulse AI — Selective Risk vs. Coverage Comparison (Fair Same-Profile Baselines)", fontsize=11, fontweight="bold")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=9)
    plt.tight_layout()
    fig1_path = figures_dir / "stage4_risk_coverage_curve.png"
    plt.savefig(fig1_path)
    plt.close()
    print(f"  Saved: {fig1_path}")

    # Figure 2: Sensor Profile Comparison Bar Chart
    plt.figure(figsize=(9, 5), dpi=150)
    p_names = list(profile_results.keys())
    p_f1s = [profile_results[p]["macro_f1"] for p in p_names]
    colors = ["#64748b", "#3b82f6", "#06b6d4", "#8b5cf6", "#10b981"]

    bars = plt.bar(p_names, p_f1s, color=colors, width=0.55)
    plt.ylabel("Macro F1-Score on Held-out Severities", fontsize=11)
    plt.title("Diagnostics Performance across Sensor Observability Profiles (Stage 4)", fontsize=12, fontweight="bold")
    plt.ylim(0, 1.0)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., h + 0.02, f"{h:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    plt.tight_layout()
    fig2_path = figures_dir / "stage4_observability_profiles_f1.png"
    plt.savefig(fig2_path)
    plt.close()
    print(f"  Saved: {fig2_path}")

    # ---------------------------------------------------------
    # PART 5: Save JSON Run Manifests
    # ---------------------------------------------------------
    run_decision_path = runs_dir / "stage4_decision_layer_eval.json"
    with open(run_decision_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": "stage4_decision_eval_01",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "target_system": "LBNL Single-Duct AHU (Simulation)",
            "test_scenarios": [s["scenario_id"] for s in TEST_SCENARIOS],
            "window_size_minutes": window_size,
            "total_fault_windows": len(total_fault_windows),
            "detected_fault_windows": len(detected_fault_windows),
            "normal_windows": len(normal_windows),
            "false_alarms": len(false_alarms),
            "b1_risk_coverage_curve": b1_curve_basic,
            "b2_risk_coverage_curve": b2_curve_basic,
            "m_basic_curve": m_curve_basic,
            "b1_valve_curve": b1_curve_valve,
            "b2_valve_curve": b2_curve_valve,
            "m_valve_curve": m_valve_curve,
            "set_metrics_m_basic": set_metrics_m_basic,
            "set_metrics_m_valve": set_metrics_m_valve
        }, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {run_decision_path}")

    run_obs_path = runs_dir / "stage4_observability_eval.json"
    with open(run_obs_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": "stage4_observability_eval_01",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "profiles_evaluated": profile_results,
            "empirical_value_delta": {
                "valve_feedback_f1_gain": round(profile_results["BASIC_PLUS_VALVE"]["macro_f1"] - profile_results["BASIC"]["macro_f1"], 4),
                "damper_feedback_f1_gain": round(profile_results["BASIC_PLUS_DAMPER"]["macro_f1"] - profile_results["BASIC"]["macro_f1"], 4),
                "both_actuators_f1_gain": round(profile_results["BASIC_PLUS_BOTH"]["macro_f1"] - profile_results["BASIC"]["macro_f1"], 4),
                "full_observability_f1_gain": round(profile_results["FULL"]["macro_f1"] - profile_results["BASIC"]["macro_f1"], 4)
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {run_obs_path}")

    print("\nStage 4 Experiments Completed Successfully!")

if __name__ == "__main__":
    run_stage4_experiments()
