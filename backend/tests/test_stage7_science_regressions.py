import json
from pathlib import Path
import numpy as np
import pytest
import joblib

from ml.adaptation.metrics import compute_regression_metrics, compute_fdd_metrics

def test_c2_model_coefficients_and_hand_parity():
    """Verify C2 affine calibrator parameters match between joblib, metadata, and hand calc."""
    models_dir = Path("models")
    joblib_path = models_dir / "csiro-ahu9-affine-v1.joblib"
    meta_path = models_dir / "csiro-ahu9-affine-v1_metadata.json"

    assert joblib_path.exists(), "C2 joblib artifact must exist"
    assert meta_path.exists(), "C2 metadata must exist"

    model = joblib.load(joblib_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    slope = meta["parameters"]["slope"]
    intercept = meta["parameters"]["intercept_degC"]

    # Verify parameters match the audited values (not the 0.582 typo!)
    assert abs(slope - 2.013821) < 1e-4, f"Expected slope ~2.0138, got {slope}"
    assert abs(intercept - (-10.110449)) < 1e-4, f"Expected intercept ~ -10.1104, got {intercept}"
    assert abs(model.slope_ - slope) < 1e-6
    assert abs(model.intercept_ - intercept) < 1e-6

    # Verify prediction on test points matches hand calculation exactly
    test_inputs = np.array([10.0, 12.0, 14.0, 16.0, 18.0])
    preds = model.predict(test_inputs)
    for val, p in zip(test_inputs, preds):
        expected = slope * val + intercept
        assert abs(p - expected) < 1e-7

def test_c1_model_fitted_bias():
    """Verify C1 constant bias parameter in joblib and metadata."""
    models_dir = Path("models")
    joblib_path = models_dir / "csiro-ahu9-bias-v1.joblib"
    meta_path = models_dir / "csiro-ahu9-bias-v1_metadata.json"

    model = joblib.load(joblib_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    fitted_bias = meta["parameters"]["fitted_bias_degC"]
    assert abs(fitted_bias - 4.593268) < 1e-4
    assert abs(model.bias_ - fitted_bias) < 1e-6

    # Test prediction
    test_inputs = np.array([12.0, 15.0])
    preds = model.predict(test_inputs)
    assert abs(preds[0] - (12.0 + fitted_bias)) < 1e-7
    assert abs(preds[1] - (15.0 + fitted_bias)) < 1e-7

def test_bias_convention_and_mae_reduction():
    """Verify residual definition and percentage reduction math."""
    y_true = np.array([15.0, 16.0, 17.0])
    y_pred = np.array([10.0, 11.0, 12.0])

    # In our project: residual = y_true - y_pred, so under-prediction gives positive bias
    met = compute_regression_metrics(y_true, y_pred)
    assert met["mean_bias_degC"] == 5.0
    assert met["mae_degC"] == 5.0

    # Percentage reduction formula
    mae_z0 = 4.4552
    mae_c2 = 1.1062
    reduction = (mae_z0 - mae_c2) / mae_z0 * 100.0
    assert abs(reduction - 75.17) < 0.1

def test_reproduction_manifest_validity():
    """Verify stage7 reproduction manifest exists and has expected hypothesis statuses."""
    manifest_path = Path("research/runs/stage7_stage6_reproduction.json")
    assert manifest_path.exists(), "Reproduction manifest must be generated"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["hypotheses_revised_evaluation"]["H4a"]["status"] == "SUPPORTED_ON_THIS_TEST"
    assert data["hypotheses_revised_evaluation"]["H4b"]["status"] == "REFUTED_ON_TEST"
    assert data["hypotheses_revised_evaluation"]["H4c"]["status"] == "PARTIALLY_SUPPORTED_WITH_LOW_SENSITIVITY"
    assert data["held_out_regression_reproduced"]["test_healthy_points_count"] == 1074

def test_safe_run_id_path_traversal():
    """Verify get_adaptation_run rejects or sanitizes path traversal attempts."""
    from backend.app.api.endpoints.adaptation import get_adaptation_run
    from fastapi import HTTPException

    # Path traversal should raise 400 or 404, not expose files outside research/runs
    with pytest.raises(HTTPException) as exc:
        get_adaptation_run("../../../windows/system32/cmd")
    assert exc.value.status_code in (400, 404)

def test_csiro_model_loading_without_transformer_error():
    """Verify CSIRO adaptation models can be loaded without raising 'Transformer file not found'."""
    from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
    engine = VirtualSensorInferenceEngine()
    for m_id in ["csiro-ahu9-bias-v1", "csiro-ahu9-affine-v1", "csiro-ahu9-residual-ridge-v1", "csiro-ahu9-local-ridge-v1", "csiro-ahu9-local-lgbm-v1"]:
        model, transformer, meta = engine.load_model(m_id)
        assert model is not None
        assert transformer is None, f"Adaptation model {m_id} should not have transformer"
        assert meta.model_id == m_id

def test_csiro_model_incompatible_scenario_blocks_inference():
    """Verify CSIRO model raises ValueError with INCOMPATIBLE_DATASET_DOMAIN on LBNL/synthetic."""
    from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
    engine = VirtualSensorInferenceEngine()
    with pytest.raises(ValueError) as exc:
        engine.predict_scenario("sc_d11cbb117b57", "csiro-ahu9-affine-v1")
    assert "INCOMPATIBLE_DATASET_DOMAIN" in str(exc.value)

def test_csiro_model_compatible_scenario_executes():
    """Verify CSIRO model executes cleanly on compatible CSIRO scenario."""
    from ml.virtual_sensor.inference import VirtualSensorInferenceEngine
    engine = VirtualSensorInferenceEngine()
    res = engine.predict_scenario("sc_89e2c6028b4f", "csiro-ahu9-affine-v1", max_points=100)
    assert res.total_points == 7666
    assert len(res.points) > 0
    assert res.model_id == "csiro-ahu9-affine-v1"
    assert res.target == "SA_TEMP"

def test_ml_models_api_lists_models_with_domain_flags():
    """Verify /api/ml/models returns target_domain and is_adaptation flags."""
    from backend.app.api.endpoints.ml import list_models
    items = list_models()
    csiro_items = [m for m in items if m.model_id.startswith("csiro-")]
    lbnl_items = [m for m in items if m.model_id.startswith("vs-sa-")]
    assert len(csiro_items) == 5
    assert len(lbnl_items) >= 4
    for m in csiro_items:
        assert m.is_adaptation is True
        assert m.target_domain == "CSIRO_AHU9"
        assert m.source_kind == "REAL_FIELD_BMS"
    for m in lbnl_items:
        assert m.is_adaptation is False
        assert m.target_domain == "LBNL_SDAHU"
