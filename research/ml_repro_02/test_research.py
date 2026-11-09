"""Unit and application integration checks for the signed-off research fixture."""
import json
import os
from pathlib import Path
import shutil

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.services import virtual_sensor_research as service
from research.ml_repro_02.gate import check

API = "/api/research/virtual-sensors"
DATE = "2018-10-20"


@pytest.fixture
def registry_dir():
    path = os.environ.get("VIRTUAL_SENSOR_RESEARCH_DIR")
    if not path:
        pytest.skip("Provide the signed-off local research registry to execute artifact tests")
    return Path(path)


@pytest.fixture
def signature(registry_dir):
    return service.digest((registry_dir / "MODEL_ARTIFACT_MANIFEST.json").read_bytes())


@pytest.fixture
def client(registry_dir, signature, monkeypatch):
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_DIR", registry_dir)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256", signature)
    return TestClient(app)


def test_metadata_and_order(client, registry_dir, signature):
    result = client.get(API)
    assert result.status_code == 200
    meta = result.json()
    assert meta["scope"] == "SIMULATED_BENCHMARK" and meta["use"] == "RESEARCH_ONLY"
    assert meta["arm"] == "PRODUCT_BASIC"
    assert set(meta["available_channels"]) == service.BASIC_CHANNELS
    assert meta["feature_order"][-3:] == list(service.CONTEXT)
    assert not {"SA_TEMP", "SYS_CTL", "CHWC_VLV", "source_label", "severity"} & set(meta["feature_order"])
    assert service.sat_model(registry_dir, signature).feature_name() == meta["feature_order"]
    assert len(meta["comparisons"]) == 8


def test_window_is_read_only_and_reports_no_eligible_minutes(client):
    assert client.post(API).status_code == 405
    assert client.post(API + "/day").status_code == 405
    assert client.get(API + "/day", params={"case": "healthy", "day": "2018-10-19"}).status_code == 404
    assert client.get(API + "/day", params={"case": "../bad", "day": DATE}).status_code == 422
    response = client.get(API + "/day", params={"case": "healthy", "day": "2018-10-22"}).json()
    assert response["status"] == "NOT_EVALUABLE" and response["reason"] == "NO_ELIGIBLE_MINUTES"
    assert response["coverage"] == 0 and response["daily_score"] is None and response["points"] == []


def test_missing_registry_returns_clear_status(monkeypatch):
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_DIR", None)
    assert TestClient(app).get(API).json() == {"detail": "RESEARCH_REGISTRY_NOT_CONFIGURED"}


def test_coverage_and_alias(client):
    for case, count, alert in (("healthy", 955, None), ("sa-plus-2", 955, "MODEL_ANOMALY")):
        response = client.get(API + "/day", params={"case": case, "day": DATE}).json()
        assert response["status"] == "EVALUATED"
        assert len(response["points"]) == response["evaluated_minutes"] == count
        assert response["coverage"] == pytest.approx(count / 1440)
        assert response["alert"] == alert
        assert response["daily_score"] == pytest.approx(sum(row["z"] for row in response["points"]) / count)
        expected = "PUBLISHER_BASELINE" if case == "healthy" else "UNVERIFIED_PUBLISHER_ALIAS"
        assert response["case"]["alias_status"] == expected


def temporary_registry(registry_dir, tmp_path, edit):
    root = shutil.copytree(registry_dir, tmp_path / "registry")
    path = root / "MODEL_ARTIFACT_MANIFEST.json"
    manifest = json.loads(path.read_text())
    edit(root, manifest)
    path.write_text(json.dumps(manifest))
    return root, service.digest(path.read_bytes())


@pytest.mark.parametrize("kind", ["source", "feature", "native-order", "bytes", "window-bytes"])
def test_corrupt_registry_is_unavailable(kind, registry_dir, tmp_path, monkeypatch):
    def edit(root, manifest):
        if kind == "source":
            manifest["source_sha256"] = "0" * 64
        elif kind in {"feature", "native-order"}:
            order = manifest["schema"]["feature_orders"]["SA_TEMP"]
            if kind == "feature":
                order[0] = "SA_TEMP"
            else:
                order[0], order[1] = order[1], order[0]
            manifest["models"]["SA_TEMP"]["feature_order"] = order
            manifest["schema_sha256"] = service.schema_digest(manifest["schema"])
        else:
            path = "SA_TEMP.lightgbm.txt" if kind == "bytes" else "healthy.parquet"
            (root / path).write_text("changed")

    root, signature = temporary_registry(registry_dir, tmp_path, edit)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_DIR", root)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256", signature)
    response = TestClient(app).get(API + "/day", params={"case": "healthy", "day": DATE})
    assert response.status_code == 503 and response.json()["detail"] == "RESEARCH_ARTIFACT_UNAVAILABLE"


def test_bad_manifest_pin(registry_dir, monkeypatch):
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_DIR", registry_dir)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256", "0" * 64)
    assert TestClient(app).get(API).status_code == 503


@pytest.mark.parametrize("kind, reason", [("missing", "MISSING_BASIC_CHANNELS: SA_TEMP"),
                                           ("constant", "CONSTANT_CALIBRATION_SCALE")])
def test_unscorable_basic_abstains(kind, reason, registry_dir, tmp_path, monkeypatch):
    def edit(root, manifest):
        if kind == "constant":
            manifest["models"]["SA_TEMP"]["abs_scale"] = None
        else:
            entry = manifest["windows"]["healthy"]
            path = root / entry["file"]
            pd.read_parquet(path).drop(columns="SA_TEMP").to_parquet(path)
            entry["sha256"] = service.digest(path.read_bytes())

    root, signature = temporary_registry(registry_dir, tmp_path, edit)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_DIR", root)
    monkeypatch.setattr(settings, "VIRTUAL_SENSOR_RESEARCH_MANIFEST_SHA256", signature)
    response = TestClient(app).get(API + "/day", params={"case": "healthy", "day": DATE}).json()
    assert response["status"] == "NOT_EVALUABLE"
    assert response["reason"] == reason
    assert response["points"] == [] and response["daily_score"] is None and response["alert"] is None
    if kind == "missing":
        assert "SA_TEMP" not in response["present_channels"]


def test_d0_rejects_mismatched_inputs(tmp_path):
    source = tmp_path / "wrong.zip"
    source.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="D0 SHA mismatch"):
        check(source, service.SOURCE_SHA)
