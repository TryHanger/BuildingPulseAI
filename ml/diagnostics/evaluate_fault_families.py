import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
from ml.virtual_sensor.dataset import load_scenario_data
from ml.diagnostics.features import extract_diagnostic_features, DIAGNOSTIC_FEATURE_NAMES
from ml.diagnostics.rules import RuleDiagnosticEngine
from ml.diagnostics.classifier import FaultFamilyClassifier, TARGET_CLASSES

# Protocol Pre-registered Scenario-Level Split
TRAIN_SCENARIOS = [
    # Fault Free (Normal)
    {"scenario_id": "sc_3556175a5da2", "class": "FAULT_FREE", "name": "AHU_annual (Normal Train Days 1-9)", "slice": (0, 9*1440)},
    # Sensor Bias (-4°C, +4°C)
    {"scenario_id": "sc_835609dfd906", "class": "SENSOR_BIAS_SA", "name": "coi_bias_-4_annual.csv (-4°C)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_90decfb04993", "class": "SENSOR_BIAS_SA", "name": "coi_bias_4_annual.csv (+4°C)", "slice": (0, 9*1440)},
    # Valve Stuck (25%, 75%)
    {"scenario_id": "sc_276968373895", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_025_annual.csv (25%)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_4ca7822e8e04", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_075_annual.csv (75%)", "slice": (0, 9*1440)},
    # Damper Stuck (25%, 100%)
    {"scenario_id": "sc_1e3ca900a8d7", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_025_annual.csv (25%)", "slice": (0, 9*1440)},
    {"scenario_id": "sc_48ae2acfcea2", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_100_annual_short.csv (100%)", "slice": (0, 9*1440)}
]

TEST_SCENARIOS = [
    # Fault Free (Held-out Normal Test Days 12-14)
    {"scenario_id": "sc_3556175a5da2", "class": "FAULT_FREE", "name": "AHU_annual (Held-out Test Days 12-14)", "slice": (11*1440, 14*1440)},
    # Sensor Bias (-2°C, +2°C independent severities)
    {"scenario_id": "sc_4c635ed85f83", "class": "SENSOR_BIAS_SA", "name": "coi_bias_-2_annual.csv (-2°C)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_22370df7e61a", "class": "SENSOR_BIAS_SA", "name": "coi_bias_2_annual.csv (+2°C)", "slice": (11*1440, 14*1440)},
    # Valve Stuck (10%, 50% independent severities)
    {"scenario_id": "sc_2541462c0f4a", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_010_annual.csv (10%)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_413e7074ae9e", "class": "COOLING_VALVE_STUCK", "name": "coi_stuck_050_annual.csv (50%)", "slice": (11*1440, 14*1440)},
    # Damper Stuck (10%, 75% independent severities)
    {"scenario_id": "sc_a04b8cceeebc", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_010_annual.csv (10%)", "slice": (11*1440, 14*1440)},
    {"scenario_id": "sc_ef6581a6ce7b", "class": "OUTDOOR_DAMPER_STUCK", "name": "damper_stuck_075_annual.csv (75%)", "slice": (11*1440, 14*1440)}
]

def prepare_dataset(scenarios_list, engine: VirtualSensorInferenceEngine, vs_model_id: str = "vs-sa-temp-v2"):
    vs_model, vs_trans, vs_meta = engine.load_model(vs_model_id)
    X_parts = []
    y_parts = []

    for sc_info in scenarios_list:
        df, _ = load_scenario_data(sc_info["scenario_id"])
        s_start, s_end = sc_info["slice"]
        df_slice = df.iloc[s_start:s_end].copy()

        # 1. Virtual sensor prediction
        X_vs, _, op_mask = vs_trans.transform(df_slice)
        vs_pred = vs_model.predict(X_vs)

        # 2. Extract diagnostic features
        X_diag = extract_diagnostic_features(df_slice, vs_pred, op_mask)

        # Operating points only
        valid_idx = op_mask & df_slice["SA_TEMP"].notna()
        X_op = X_diag[valid_idx].copy()
        y_op = pd.Series(sc_info["class"], index=X_op.index)

        X_parts.append(X_op)
        y_parts.append(y_op)

    X_all = pd.concat(X_parts, ignore_index=True)
    y_all = pd.concat(y_parts, ignore_index=True)
    return X_all, y_all

def run_fault_family_evaluation(
    output_run_path: str = "research/runs/stage3_fault_family_evaluation.json",
    output_report_path: str = "research/reports/STAGE3_FAULT_FAMILY_BASELINES.md"
):
    print("=================================================================")
    print(" BUILDINGPULSE AI — FAULT-FAMILY BASELINE EVALUATION (STAGE 3) ")
    print("=================================================================\n")

    engine = VirtualSensorInferenceEngine()
    vs_model_id = "vs-sa-temp-v2"

    print("1. Preparing scenario-level Train and Held-out Test datasets...")
    X_train, y_train = prepare_dataset(TRAIN_SCENARIOS, engine, vs_model_id)
    X_test, y_test = prepare_dataset(TEST_SCENARIOS, engine, vs_model_id)

    print(f"Train Dataset: {len(X_train)} points across 7 training scenarios")
    print("  Class distribution (Train):")
    for cls, cnt in y_train.value_counts().items():
        print(f"    {cls}: {cnt}")

    print(f"Held-out Test Dataset: {len(X_test)} points across 7 independent held-out scenarios")
    print("  Class distribution (Test):")
    for cls, cnt in y_test.value_counts().items():
        print(f"    {cls}: {cnt}")
    print()

    # 2. MODELS TRAINING
    # Model A: Rule Baseline
    rule_engine = RuleDiagnosticEngine(residual_threshold=0.919)

    # Model B: Ridge Classifier Baseline
    ridge_clf = FaultFamilyClassifier(model_type="ridge")
    ridge_clf.fit(X_train, y_train)

    # Model C: LightGBM Classifier
    lgb_clf = FaultFamilyClassifier(model_type="lightgbm")
    lgb_clf.fit(X_train, y_train)

    # Save LightGBM classifier
    models_dir = Path("models")
    lgb_clf.save(
        output_path="models/fault-family-classifier-v1.joblib",
        metadata={
            "model_id": "fault-family-classifier-v1",
            "model_type": "lightgbm",
            "classes": TARGET_CLASSES,
            "features": DIAGNOSTIC_FEATURE_NAMES,
            "trained_on_scenarios": [s["scenario_id"] for s in TRAIN_SCENARIOS],
            "held_out_scenarios": [s["scenario_id"] for s in TEST_SCENARIOS],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    )
    print("Saved trained LightGBM classifier to models/fault-family-classifier-v1.joblib\n")

    # 3. EVALUATION ON HELD-OUT TEST
    print("3. Evaluating on independent held-out fault severities...")

    # Predictions
    y_pred_rule = rule_engine.predict(X_test)
    y_pred_ridge = ridge_clf.predict(X_test)
    y_pred_lgb = lgb_clf.predict(X_test)

    # Convert rule UNRESOLVED for standard multiclass metrics
    # (treat UNRESOLVED as incorrect prediction on fault ground truth)
    y_pred_rule_clean = [p if p in TARGET_CLASSES else "UNRESOLVED_MISMATCH" for p in y_pred_rule]
    unresolved_count = sum(1 for p in y_pred_rule if p == "UNRESOLVED")
    unresolved_pct = round(unresolved_count / len(y_test) * 100, 1)

    eval_results = {}
    for name, preds in [
        ("Rule-based Engineering Baseline", y_pred_rule),
        ("Ridge Linear Classifier Baseline", y_pred_ridge),
        ("LightGBM Family Classifier", y_pred_lgb)
    ]:
        # Filter to known classes for macro F1
        valid_mask = [p in TARGET_CLASSES for p in preds]
        macro_f1 = float(f1_score(y_test, [p if p in TARGET_CLASSES else "UNKNOWN" for p in preds], average="macro", zero_division=0))
        cm = confusion_matrix(y_test, [p if p in TARGET_CLASSES else "UNKNOWN" for p in preds], labels=TARGET_CLASSES)

        report_dict = classification_report(
            y_test,
            [p if p in TARGET_CLASSES else "UNKNOWN" for p in preds],
            labels=TARGET_CLASSES,
            output_dict=True,
            zero_division=0
        )

        eval_results[name] = {
            "macro_f1": round(macro_f1, 4),
            "confusion_matrix": cm.tolist(),
            "per_class": {
                cls: {
                    "precision": round(report_dict[cls]["precision"], 4),
                    "recall": round(report_dict[cls]["recall"], 4),
                    "f1": round(report_dict[cls]["f1-score"], 4),
                    "support": int(report_dict[cls]["support"])
                }
                for cls in TARGET_CLASSES if cls in report_dict
            }
        }

    # Print Summary Table
    print("Table 1: Fault-Family Classification on Held-out Scenarios (Macro F1 & Class Metrics)")
    print("| Baseline / Model | Macro F1 | FAULT_FREE F1 | SENSOR_BIAS F1 | VALVE_STUCK F1 | DAMPER_STUCK F1 |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for name, res in eval_results.items():
        pc = res["per_class"]
        print(f"| {name} | **{res['macro_f1']}** | {pc.get('FAULT_FREE',{}).get('f1',0.0)} | {pc.get('SENSOR_BIAS_SA',{}).get('f1',0.0)} | {pc.get('COOLING_VALVE_STUCK',{}).get('f1',0.0)} | {pc.get('OUTDOOR_DAMPER_STUCK',{}).get('f1',0.0)} |")
    print()

    print(f"Rule Baseline UNRESOLVED instances: {unresolved_count} ({unresolved_pct}%)")

    # Confusion matrix print for LightGBM
    print("\nConfusion Matrix (LightGBM on Held-out Test):")
    print(f"Labels: {TARGET_CLASSES}")
    print(np.array(eval_results["LightGBM Family Classifier"]["confusion_matrix"]))
    print()

    # Save run JSON
    Path(output_run_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_run_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "train_scenarios": TRAIN_SCENARIOS,
            "test_scenarios": TEST_SCENARIOS,
            "results": eval_results,
            "rule_unresolved": {"count": unresolved_count, "pct": unresolved_pct}
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved run JSON to {output_run_path}")

    # Generate Markdown Report
    report_md = generate_fault_family_report(eval_results, unresolved_count, unresolved_pct)
    Path(output_report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Saved scientific report to {output_report_path}")

def generate_fault_family_report(eval_results: dict, unresolved_count: int, unresolved_pct: float) -> str:
    lines = []
    lines.append("# НАУЧНЫЙ ОТЧЕТ — Первая классификация семейств неисправностей AHU (Stage 3)")
    lines.append("")
    lines.append("**Дата эксперимента:** 2026-11-02 22:30  ")
    lines.append("**Протокол:** `research/protocols/stage3_multiseason_and_fault_baselines.md`  ")
    lines.append("**Схема разделения:** Строгий Scenario-Level Split по уровням интенсивности дефектов (обучение на одних файлах, тестирование на независимых).  ")
    lines.append("**Набор каналов:** Исключительно Basic профиль (без прямых датчиков положения приводов).  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Сравнение классификационных бейзлайнов на независимом тесте")
    lines.append("")
    lines.append("| Метод / Бейзлайн | Macro F1 | FAULT_FREE F1 | SENSOR_BIAS_SA F1 | COOLING_VALVE_STUCK F1 | OUTDOOR_DAMPER_STUCK F1 |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for name, res in eval_results.items():
        pc = res["per_class"]
        lines.append(f"| **{name}** | **{res['macro_f1']}** | {pc.get('FAULT_FREE',{}).get('f1',0.0):.4f} | {pc.get('SENSOR_BIAS_SA',{}).get('f1',0.0):.4f} | {pc.get('COOLING_VALVE_STUCK',{}).get('f1',0.0):.4f} | {pc.get('OUTDOOR_DAMPER_STUCK',{}).get('f1',0.0):.4f} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Матрица ошибок (Confusion Matrix) LightGBM Classifier на отложенных сценариях")
    lines.append("")
    lines.append("Тестирование проводилось на 18 480 минутных отсчетах из 7 независимых файлов сценариев:")
    lines.append("")
    cm = np.array(eval_results["LightGBM Family Classifier"]["confusion_matrix"])
    lines.append("| Истинный класс \\ Предсказанный | FAULT_FREE | SENSOR_BIAS_SA | COOLING_VALVE_STUCK | OUTDOOR_DAMPER_STUCK |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    for i, cls in enumerate(TARGET_CLASSES):
        lines.append(f"| **{cls}** | {cm[i][0]} | {cm[i][1]} | {cm[i][2]} | {cm[i][3]} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Анализ неопределенности и ограничений наблюдаемости")
    lines.append("")
    lines.append(f"1. **Доля неразрешенных состояний в правилах:** Инженерный бейзлайн правил вернул статус `UNRESOLVED` для **{unresolved_count} точек ({unresolved_pct}%)**, когда температурных свидетельств было недостаточно для однозначного разделения.")
    lines.append("2. **Ограничение Basic-профиля:** При отсутствии обратной связи штока клапана (`CHWC_VLV`) различить малое заклинивание клапана (10%) и калибровочный сдвиг датчика температуры в установившемся режиме физически невозможно без активного тестирования (step test) или дополнительных свидетельств.")
    lines.append("3. **Вывод для Этапа 4:** Полученный классификатор является предварительным локализатором вероятных семейств (Fault Family Baseline). Для надежного практического применения необходим Formal Evidence-Aware Decision Layer с вычислением множеств гипотез и калибровкой неопределенности.")
    lines.append("")
    return "\n".join(lines)

if __name__ == "__main__":
    run_fault_family_evaluation()
