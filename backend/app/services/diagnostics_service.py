import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd
import joblib
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import Scenario, Dataset, DiagnosticEvent
from backend.app.schemas.diagnostics import (
    DiagnosticEventRead,
    ScenarioDiagnosticSummary,
    DetectionSummary,
    LocalizationSummary,
    DiagnosticProvenance,
    GroundTruthEvaluationInfo,
    SensorProfileItem
)
from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
from ml.diagnostics.features import extract_diagnostic_features
from ml.diagnostics.rules import RuleDiagnosticEngine
from ml.diagnostics.classifier import FaultFamilyClassifier, TARGET_CLASSES
from ml.diagnostics.sensor_profiles import (
    SensorProfileRegistry,
    extract_profile_diagnostic_features
)
from ml.diagnostics.evidence import EvidenceEvaluator
from ml.diagnostics.decision_layer import EvidenceAwareDecisionLayer

CLASS_TRANSLATION_RU = {
    "FAULT_FREE": "Нормальный режим (дефектов не обнаружено)",
    "SENSOR_BIAS_SA": "Смещение датчика температуры притока (SA Temp Sensor Bias)",
    "COOLING_VALVE_STUCK": "Заклинивание штока клапана охлаждения (Cooling Valve Stuck)",
    "OUTDOOR_DAMPER_STUCK": "Заклинивание заслонки наружного воздуха (Outdoor Damper Stuck)",
    "UNRESOLVED": "Неопределенная группа (недостаточно свидетельств в профиле)",
    "SINGLE_CAUSE": "Однозначно локализованная причина",
    "MULTIPLE_PLAUSIBLE": "Несколько возможных причин (структурная неоднозначность)"
}

class DiagnosticsService:
    @staticmethod
    def list_sensor_profiles() -> List[SensorProfileItem]:
        profiles = SensorProfileRegistry.list_profiles()
        return [SensorProfileItem(**p) for p in profiles]

    @staticmethod
    def get_scenario_diagnostic_summary(
        db: Session,
        scenario_id: str,
        model_id: str = "vs-sa-temp-v2",
        threshold_policy: str = "three_sigma",
        profile_id: str = "BASIC",
        allow_unvalidated: bool = False
    ) -> ScenarioDiagnosticSummary:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

        dataset = db.query(Dataset).filter(Dataset.id == scenario.dataset_id).first()
        source_kind = dataset.source_kind if dataset else "UNKNOWN"

        # Check Domain Guard
        is_lbnl_benchmark = (source_kind == "SIMULATED_BENCHMARK")
        is_synthetic_demo = (source_kind == "SYNTHETIC_DEMO")

        domain_status = "VALIDATED_ON_LBNL" if is_lbnl_benchmark else "OUT_OF_DOMAIN_UNVALIDATED"
        domain_warning = None

        if not is_lbnl_benchmark:
            domain_warning = (
                "Модель обучена на симуляционном бенчмарке LBNL SD-AHU. "
                f"Для источника '{source_kind}' ML-диагностика не валидирована."
            )

        # Profile info
        try:
            profile_obj = SensorProfileRegistry.get_profile(profile_id)
            profile_item = SensorProfileItem(**profile_obj.to_dict())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # If not benchmark and unvalidated mode is NOT allowed by user toggle:
        if not is_lbnl_benchmark and not allow_unvalidated:
            return ScenarioDiagnosticSummary(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                source_kind=source_kind,
                model_domain_status="OUT_OF_DOMAIN_UNVALIDATED",
                domain_warning=domain_warning,
                profile_id=profile_id,
                profile_info=profile_item,
                detection=DetectionSummary(
                    status="OUT_OF_DOMAIN",
                    method="DOMAIN_GUARD",
                    observed_at=None,
                    score=None,
                    threshold=None,
                    unit="degC",
                    alarm_minutes=0,
                    alarm_episodes_count=0,
                    operating_minutes=0
                ),
                localization=LocalizationSummary(
                    status="NOT_EVALUATED",
                    decision_status="OUT_OF_DOMAIN",
                    candidate_class=None,
                    candidate_class_ru="Диагностика отключена (несовместимый домен)",
                    single_cause=None,
                    candidate_causes=[],
                    score=None,
                    score_type="domain_guard_disabled",
                    supporting_evidence=[],
                    missing_evidence=["Требуется явное включение исследовательского режима UNVALIDATED_OUT_OF_DOMAIN"],
                    limitations=[
                        "Модель обучена на симуляционном бенчмарке EnergyPlus Chicago TMY и не валидирована для полевых данных реального здания без адаптации"
                    ],
                    reason_codes=["OUT_OF_DOMAIN_BENCHMARK"]
                ),
                provenance=DiagnosticProvenance(
                    dataset_version=str(dataset.sha256[:16]) if dataset and dataset.sha256 else "unknown",
                    model_id=model_id,
                    model_version="stage4-v1",
                    threshold_policy=threshold_policy,
                    feature_profile=profile_id,
                    scientific_disclaimer="Внимание: Доменный барьер Domain Guard заблокировал выдачу ML-заключений для невалидированного источника."
                ),
                ground_truth=GroundTruthEvaluationInfo(
                    source_fault_label=scenario.source_fault_label,
                    source_fault_label_type=scenario.source_fault_label_type,
                    description=scenario.description,
                    is_benchmark_evaluation=is_lbnl_benchmark
                )
            )

        # Perform Detection via Virtual Sensor
        engine = VirtualSensorInferenceEngine()
        pred_res = engine.predict_scenario(
            scenario_id=scenario_id,
            model_id=model_id,
            threshold_policy=threshold_policy,
            max_points=None  # Full resolution
        )

        parquet_path = settings.scenario_data_path(scenario.data_path)
        df_raw = pd.read_parquet(parquet_path)

        vs_preds = np.array([p.predicted if p.predicted is not None else 0.0 for p in pred_res.points])
        op_mask = pd.Series([p.is_operating for p in pred_res.points], index=df_raw.index)
        op_indices = np.where(op_mask.values)[0]

        # Extract features for requested profile using strict isolation
        X_profile_feats, feat_names = extract_profile_diagnostic_features(
            df_raw, vs_preds, profile_id=profile_id
        )

        # Evidence Evaluator for active profile
        allowed_ch = set(SensorProfileRegistry.get_allowed_channels(profile_id))
        evaluator = EvidenceEvaluator(allowed_ch)
        evidence_list = evaluator.evaluate_window_evidence(
            df_raw, vs_preds, pred_res.threshold_value or 0.919, op_mask.values
        )

        # Check for profile-specific model in models/
        profile_model_path = Path(f"models/classifier_{profile_id.lower()}.joblib")
        classifier = None
        if profile_model_path.exists():
            try:
                loaded = joblib.load(str(profile_model_path))
                classifier = loaded["model"]
            except Exception:
                classifier = None

        if classifier is None:
            # Fallback to stage 3 classifier
            clf_path = Path("models/fault-family-classifier-v1.joblib")
            if clf_path.exists():
                try:
                    classifier, _ = FaultFamilyClassifier.load(str(clf_path))
                except Exception:
                    classifier = None

        # Predict fault probabilities
        anomaly_detected = (pred_res.alarm_points > 0)
        class_probs = {"FAULT_FREE": 1.0}

        if classifier is not None and len(op_indices) > 0:
            if anomaly_detected:
                alarm_idx = [i for i in op_indices if pred_res.points[i].is_alarm]
                eval_idx = alarm_idx if len(alarm_idx) > 0 else op_indices
            else:
                eval_idx = op_indices

            X_eval = X_profile_feats.iloc[eval_idx]
            # Ensure model features match
            if hasattr(classifier, "feature_names_in_") and classifier.feature_names_in_ is not None:
                model_feats = list(classifier.feature_names_in_)
            else:
                model_feats = list(feat_names)
            common_feats = [f for f in model_feats if f in X_eval.columns]
            if len(common_feats) == len(model_feats):
                X_input = X_eval[common_feats]
                proba_mean = classifier.predict_proba(X_input).mean(axis=0)
                classes = getattr(classifier, "classes_", TARGET_CLASSES)
                class_probs = {c: float(proba_mean[i]) for i, c in enumerate(classes)}
            else:
                # If feature mismatch, predict on default features
                proba_mean = [0.25, 0.25, 0.25, 0.25]
                class_probs = {c: float(proba_mean[i]) for i, c in enumerate(TARGET_CLASSES)}

        # Evaluate via EvidenceAwareDecisionLayer
        decision_layer = EvidenceAwareDecisionLayer()
        decision_res = decision_layer.evaluate(
            domain_status="VALIDATED" if is_lbnl_benchmark or allow_unvalidated else "OUT_OF_DOMAIN",
            is_operating=(pred_res.operating_points > 0),
            anomaly_detected=anomaly_detected,
            classifier_probs=class_probs,
            evidence_list=evidence_list,
            profile_id=profile_id
        )

        det_status = "ANOMALY" if anomaly_detected else "NORMAL"
        cand_class = decision_res.get("single_cause") or (
            decision_res.get("candidate_causes")[0] if len(decision_res.get("candidate_causes", [])) > 0 else "UNRESOLVED"
        )
        if not anomaly_detected:
            cand_class = "FAULT_FREE"

        supporting = [
            f"Зафиксировано {pred_res.alarm_points} минут температурного отклонения ({pred_res.alarm_episodes_count} эпизодов)",
            f"Максимальная невязка: {(pred_res.metrics or {}).get('max_residual_abs', 0.0):.2f}°C при пороге {pred_res.threshold_value:.2f}°C",
            f"Статус Decision Layer: {decision_res['status']}"
        ]
        if decision_res.get("single_cause"):
            supporting.append(f"Локализованная причина: {CLASS_TRANSLATION_RU.get(decision_res['single_cause'], decision_res['single_cause'])}")
        elif len(decision_res.get("candidate_causes", [])) > 1:
            supporting.append(f"Возможные конкурирующие причины: {', '.join([CLASS_TRANSLATION_RU.get(c, c) for c in decision_res['candidate_causes']])}")

        provenance = DiagnosticProvenance(
            dataset_version=str(dataset.sha256[:16]) if dataset and dataset.sha256 else "unknown",
            model_id=model_id,
            model_version="stage4-v1",
            threshold_policy=threshold_policy,
            feature_profile=profile_id,
            scientific_disclaimer="Вывод Decision Layer основан на совместной верификации невязок модели, физических свидетельств и доступности каналов активного профиля."
        )

        ground_truth = GroundTruthEvaluationInfo(
            source_fault_label=scenario.source_fault_label,
            source_fault_label_type=scenario.source_fault_label_type,
            description=scenario.description,
            is_benchmark_evaluation=is_lbnl_benchmark
        )

        return ScenarioDiagnosticSummary(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            source_kind=source_kind,
            model_domain_status=domain_status,
            domain_warning=domain_warning,
            profile_id=profile_id,
            profile_info=profile_item,
            detection=DetectionSummary(
                status=det_status,
                method="RESIDUAL_AND_PHYSICS",
                observed_at=pred_res.points[op_indices[0]].timestamp if len(op_indices) > 0 else None,
                score=round(pred_res.metrics.get("max_residual_abs", 0.0), 3),
                threshold=pred_res.threshold_value,
                unit="degC",
                alarm_minutes=pred_res.alarm_points,
                alarm_episodes_count=pred_res.alarm_episodes_count,
                operating_minutes=pred_res.operating_points
            ),
            localization=LocalizationSummary(
                status=decision_res["status"],
                decision_status=decision_res["status"],
                candidate_class=cand_class,
                candidate_class_ru=CLASS_TRANSLATION_RU.get(cand_class, cand_class),
                single_cause=decision_res.get("single_cause"),
                single_cause_ru=CLASS_TRANSLATION_RU.get(decision_res.get("single_cause") or "", None),
                candidate_causes=decision_res.get("candidate_causes", []),
                score=round(float(max(class_probs.values())), 3),
                score_type="decision_layer_score",
                supporting_evidence=supporting,
                missing_evidence=decision_res.get("missing_measurements", []),
                limitations=decision_res.get("limitations", []),
                reason_codes=decision_res.get("reason_codes", []),
                structured_evidence=decision_res.get("evidence", []),
                missing_measurements=decision_res.get("missing_measurements", [])
            ),
            provenance=provenance,
            ground_truth=ground_truth
        )

    @staticmethod
    def run_baseline_rules(
        db: Session,
        scenario_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[DiagnosticEventRead]:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

        parquet_path = settings.scenario_data_path(scenario.data_path)

        if not parquet_path.exists():
            raise HTTPException(status_code=404, detail="Data file not found")

        df = pd.read_parquet(parquet_path)
        if len(df) == 0:
            return []

        time_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df[time_col] = df[time_col].astype(str)

        if start_time:
            df = df[df[time_col] >= start_time]
        if end_time:
            df = df[df[time_col] <= end_time]

        engine = VirtualSensorInferenceEngine()
        pred_res = engine.predict_scenario(
            scenario_id=scenario_id,
            model_id="vs-sa-temp-v2",
            threshold_policy="three_sigma"
        )
        vs_preds = np.array([p.predicted if p.predicted is not None else 0.0 for p in pred_res.points])
        op_mask = pd.Series([p.is_operating for p in pred_res.points], index=df.index)

        X_diag = extract_diagnostic_features(df, vs_preds, op_mask)
        rule_engine = RuleDiagnosticEngine(residual_threshold=pred_res.threshold_value or 0.919)
        preds = rule_engine.predict(X_diag)

        events: List[DiagnosticEventRead] = []
        in_event = False
        cur_event_type = None
        ev_start = None

        for idx, p in enumerate(preds):
            if p != "FAULT_FREE":
                if not in_event:
                    in_event = True
                    cur_event_type = p
                    ev_start = str(df.iloc[idx][time_col])
            else:
                if in_event:
                    ev_end = str(df.iloc[idx - 1][time_col])
                    events.append(
                        DiagnosticEventRead(
                            id=str(uuid.uuid4())[:12],
                            scenario_id=scenario_id,
                            started_at=ev_start,
                            ended_at=ev_end,
                            rule_id=f"RULE_{cur_event_type}",
                            severity="HIGH" if cur_event_type != "UNRESOLVED" else "MEDIUM",
                            evidence_json={"predicted_class": cur_event_type},
                            conclusion_type="PHYSICAL_BASELINE",
                            generated_by_version="stage4-rules-v1"
                        )
                    )
                    in_event = False

        if in_event:
            events.append(
                DiagnosticEventRead(
                    id=str(uuid.uuid4())[:12],
                    scenario_id=scenario_id,
                    started_at=ev_start,
                    ended_at=str(df.iloc[-1][time_col]),
                    rule_id=f"RULE_{cur_event_type}",
                    severity="HIGH" if cur_event_type != "UNRESOLVED" else "MEDIUM",
                    evidence_json={"predicted_class": cur_event_type},
                    conclusion_type="PHYSICAL_BASELINE",
                    generated_by_version="stage4-rules-v1"
                )
            )

        return events

    @staticmethod
    def get_events(
        db: Session,
        scenario_id: str,
        conclusion_type: Optional[str] = None
    ) -> List[DiagnosticEventRead]:
        query = db.query(DiagnosticEvent).filter(DiagnosticEvent.scenario_id == scenario_id)
        if conclusion_type:
            query = query.filter(DiagnosticEvent.conclusion_type == conclusion_type)
        events = query.order_by(DiagnosticEvent.started_at).all()
        return [DiagnosticEventRead.model_validate(e) for e in events]
