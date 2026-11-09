import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.diagnostics.features import DIAGNOSTIC_FEATURE_NAMES

TARGET_CLASSES = [
    "FAULT_FREE",
    "SENSOR_BIAS_SA",
    "COOLING_VALVE_STUCK",
    "OUTDOOR_DAMPER_STUCK"
]

class FaultFamilyClassifier:
    """
    Multiclass fault-family diagnostic classifier for Basic AHU telemetry.
    Supports LightGBM and Linear (RidgeClassifier) architectures.
    """
    def __init__(
        self,
        model_type: str = "lightgbm",
        random_state: int = 42
    ):
        self.model_type = model_type
        self.random_state = random_state
        self.classes_ = TARGET_CLASSES
        self.model = None

        if model_type == "lightgbm":
            self.model = lgb.LGBMClassifier(
                n_estimators=80,
                learning_rate=0.05,
                max_depth=4,
                num_leaves=15,
                min_child_samples=30,
                random_state=random_state,
                objective="multiclass",
                num_class=len(TARGET_CLASSES),
                verbose=-1
            )
        elif model_type == "ridge":
            self.model = Pipeline([
                ("scaler", StandardScaler()),
                ("clf", RidgeClassifier(alpha=1.0, random_state=random_state))
            ])
        else:
            raise ValueError(f"Unknown classifier model_type: {model_type}")

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FaultFamilyClassifier":
        X_clean = X[DIAGNOSTIC_FEATURE_NAMES].fillna(0.0)
        self.model.fit(X_clean, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = X[DIAGNOSTIC_FEATURE_NAMES].fillna(0.0)
        return self.model.predict(X_clean)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = X[DIAGNOSTIC_FEATURE_NAMES].fillna(0.0)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X_clean)
        elif hasattr(self.model, "decision_function"):
            dfn = self.model.decision_function(X_clean)
            if dfn.ndim == 1:
                dfn = np.column_stack([-dfn, dfn])
            # Softmax
            exp_dfn = np.exp(dfn - np.max(dfn, axis=1, keepdims=True))
            return exp_dfn / np.sum(exp_dfn, axis=1, keepdims=True)
        else:
            n = len(X_clean)
            return np.full((n, len(self.classes_)), 1.0 / len(self.classes_))

    def save(self, output_path: str, metadata: dict):
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, p)

        meta_path = p.with_suffix(".json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, model_path: str) -> Tuple["FaultFamilyClassifier", dict]:
        p = Path(model_path)
        model = joblib.load(p)
        meta_path = p.with_suffix(".json")
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        m_type = meta.get("model_type", "lightgbm")
        inst = cls(model_type=m_type)
        inst.model = model
        inst.classes_ = meta.get("classes", TARGET_CLASSES)
        return inst, meta
