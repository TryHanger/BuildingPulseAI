"""Abstention, artifact integrity and FDD boundary regression checks."""
import pandas as pd
import pytest

from backend.app.services import virtual_sensor_research as service
from backend.app.services.sat_daily_coverage import POLICY_VERSION, assess
from research.ml_repro_02.test_research import API, DATE, client, registry_dir, signature, temporary_registry


@pytest.mark.parametrize("minutes,running,status", [
    ([], 0, "NOT_EVALUABLE"),
    ([8], 1, "INSUFFICIENT_COVERAGE"),
    (range(119), 119, "INSUFFICIENT_COVERAGE"),
    (list(range(0, 240, 2)), 120, "INSUFFICIENT_COVERAGE"),
    (range(120), 151, "INSUFFICIENT_COVERAGE"),
    (range(120), 150, "EVALUATED"),
])
def test_predeclared_daily_policy(minutes, running, status):
    assert assess(minutes, running).status == status


@pytest.mark.parametrize("minutes", [[10, 9], [10, 10], [1440]])
def test_policy_rejects_invalid_clock(minutes):
    with pytest.raises(ValueError, match="source-clock minute order"):
        assess(minutes, 2)


@pytest.mark.parametrize("kind, status, reason", [
    ("single", "INSUFFICIENT_COVERAGE", "DAILY_COVERAGE_FLOOR"),
    ("fragment", "INSUFFICIENT_COVERAGE", "DAILY_COVERAGE_FLOOR"),
    ("nan", "NOT_EVALUABLE", "NONFINITE_BASIC_INPUTS"),
    ("unknown_fan", "NOT_EVALUABLE", "UNKNOWN_FAN_TIMELINE"),
    ("missing", "NOT_EVALUABLE", "MISSING_BASIC_CHANNELS: OA_TEMP"),
])
def test_archive_abstention(kind, status, reason, registry_dir, tmp_path):
    def edit(root, manifest):
        entry = manifest["windows"]["sa-plus-2"]
        path = root / entry["file"]
        frame = pd.read_parquet(path)
        day = frame.timestamp.dt.strftime("%Y-%m-%d") == DATE
        eligible = frame.index[day & frame.eligible]
        if kind in {"single", "fragment"}:
            kept = eligible[:1] if kind == "single" else eligible[::2]
            frame.loc[eligible.difference(kept), "eligible"] = False
        elif kind == "nan":
            frame.loc[eligible, "OA_TEMP"] = float("nan")
        elif kind == "unknown_fan":
            frame.loc[eligible[0], "SF_SPD_DM"] = float("nan")
        else:
            frame = frame.drop(columns="OA_TEMP")
        frame.to_parquet(path)
        entry["sha256"] = service.digest(path.read_bytes())

    root, pin = temporary_registry(registry_dir, tmp_path, edit)
    result = service.infer(root, pin, "sa-plus-2", DATE)
    assert (result.status, result.reason) == (status, reason)
    assert result.daily_score is None and result.alert is None
    assert result.metadata.policy_version == POLICY_VERSION == "sat-daily-coverage@1.0.0"
    if kind == "single":
        assert result.evaluated_minutes == 1 and result.points[0].z > 3
    if kind == "fragment":
        assert result.evaluated_minutes > 120 and result.continuous_minutes == 1


def test_archive_rejects_unsorted_timestamps(registry_dir, tmp_path):
    def edit(root, manifest):
        entry = manifest["windows"]["healthy"]
        path = root / entry["file"]
        pd.read_parquet(path).iloc[::-1].to_parquet(path)
        entry["sha256"] = service.digest(path.read_bytes())

    root, pin = temporary_registry(registry_dir, tmp_path, edit)
    with pytest.raises(service.ArtifactError, match="Window clock"):
        service.infer(root, pin, "healthy", DATE)


def test_after_warmup_registry_sha_is_still_checked(registry_dir, tmp_path):
    root, pin = temporary_registry(registry_dir, tmp_path, lambda *_: None)
    service.infer(root, pin, "healthy", DATE)
    with (root / "SA_TEMP.lightgbm.txt").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(service.ArtifactError, match="Artifact SHA mismatch"):
        service.infer(root, pin, "healthy", DATE)


def test_policy_cannot_be_supplied_by_registry(registry_dir, tmp_path):
    def edit(root, manifest):
        manifest["policy_version"] = "unauthorized@2.0.0"

    root, pin = temporary_registry(registry_dir, tmp_path, edit)
    assert service.registry(root, pin)[2].policy_version == "sat-daily-coverage@1.0.0"


def test_research_alarm_cannot_enter_fdd_feed(client):
    manifest = client.get(API).json()
    assert {method["id"] for method in manifest["methods"]} == {
        "SAT_ONLY", "SYSTEM_MAX_8", "SAT_MINUS_SETPOINT",
    }
    assert {row["evidence"] for row in manifest["comparisons"]} == {"REPRO_01_SAVED_DAILY_CSV"}
    dataset_id = "ds_8e5b1ddfdd14"
    query = {"dataset_id": dataset_id, "start": "2018-01-02T11:08:00", "limit": 1}
    before = client.get("/api/v1/incidents", params=query)
    assert before.status_code == 200
    alert = client.get(API + "/day", params={"case": "sa-plus-2", "day": DATE}).json()
    assert alert["alert"] == "MODEL_ANOMALY" and alert["method"] == "SAT_ONLY"
    assert client.post("/api/v1/incidents", params=query, json=alert).status_code == 405
    after = client.get("/api/v1/incidents", params=query)
    assert after.json() == before.json()
    assert "MODEL_ANOMALY" not in after.text
