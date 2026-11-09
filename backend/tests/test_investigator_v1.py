import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.app.core.config import settings
from backend.app.db.models import Dataset
from backend.app.db.session import SessionLocal
from backend.app.services import investigator_v1 as runtime
from contracts.evidence_v1 import OPENAPI, validate_schema


def dataset(client):
    result = client.get("/api/v1/datasets")
    assert result.status_code == 200
    validate_schema(result.json(), "RuntimeDatasetList")
    return next(item for item in result.json()["items"] if item["name"] == "AHU_annual.csv")


def test_catalog_series_and_diagnostics_from_verified_bytes(client):
    item = dataset(client)
    dataset_id = item["dataset_id"]
    source = runtime.source_path(runtime.SOURCES[dataset_id])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item["source_sha256"]
    assert item["pair_status"] == "PAIR_NOT_VERIFIED"
    for panel in ("BASIC", "EXTRA"):
        result = client.get(f"/api/v1/datasets/{dataset_id}/signals", params={"panel": panel})
        assert result.status_code == 200
        validate_schema(result.json(), "RuntimeSignalList")
        catalog = {entry["canonical_id"]: entry for entry in result.json()["items"]}
        assert "SYS_CTL" not in catalog
        assert ("CHWC_VLV" in catalog) == (panel == "EXTRA")
        if panel == "EXTRA":
            assert catalog["CHWC_VLV"]["origin"] == "EXTRA_SIMULATED"
    params = {"dataset_id": dataset_id, "signal_ids": ["SA_TEMP", "CHWC_VLV_DM"], "limit": 2}
    result = client.get("/api/v1/series", params=params)
    assert result.status_code == 200
    payload = result.json()
    validate_schema(payload, "RuntimeSeries")
    assert payload["clock_kind"] == "SOURCE_SIMULATION_TIME"
    assert payload["timestamps"] == ["2018-01-01T01:00:00", "2018-01-01T01:01:00"]
    assert payload["signals"][0]["values"][0] == pytest.approx((66.37468 - 32) * 5 / 9)
    assert payload["signals"][1]["values"][0] == 0
    assert payload["next_start"] == "2018-01-01T01:02:00"
    for forbidden in ("SYS_CTL", "CHWC_VLV"):
        result = client.get("/api/v1/series", params={**params, "signal_ids": forbidden})
        assert result.status_code == 422
        validate_schema(result.json(), "RuntimeError")
    for invalid in ("2018-01-01T01:00:00Z", "2018-02-30T01:00:00"):
        response = client.get("/api/v1/series", params={**params, "start": invalid})
        assert response.status_code == 422
        validate_schema(response.json(), "RuntimeError")
    result = client.get("/api/v1/diagnostics", params={"dataset_id": dataset_id, "at": payload["timestamps"][0]})
    assert result.status_code == 200
    diagnosis = result.json()
    validate_schema(diagnosis, "RuntimeDiagnostics")
    rejected = client.get("/api/v1/diagnostics", params={
        "dataset_id": dataset_id, "at": payload["timestamps"][0],
        "model_scope": "IN_SCOPE", "mode": "COOLING", "validated_discriminator": "invented",
    })
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "UNKNOWN_DIAGNOSTICS_PARAMETER"
    assert diagnosis["mode"] == "OFF"
    assert diagnosis["display_state"] == "NOT_EVALUABLE"
    assert diagnosis["model_scope"] == "UNKNOWN"
    assert diagnosis["cause_status"] == "NOT_ASSESSED"
    assert all(worker["predicate"] == "INDETERMINATE" for worker in diagnosis["methods"])


def test_openapi_public_operations_match_actual_routes(client):
    app = client.app
    assert client.get("/api/v1/openapi.json").json() == OPENAPI
    actual = {(method, route.path) for route in app.routes if hasattr(route, "methods")
              and route.path.startswith("/api/v1/") and route.path != "/api/v1/openapi.json"
              for method in route.methods}
    declared = {(method.upper(), path) for path, methods in OPENAPI["paths"].items() for method in methods}
    # Newer FastAPI may keep nested routers lazy until it expands the OpenAPI route list.
    if not actual:
        from fastapi.routing import APIRoute
        from backend.app.api.endpoints.investigator_v1 import router
        actual = {(method, "/api" + route.path) for route in router.routes
                  if isinstance(route, APIRoute) and route.path != "/v1/openapi.json" for method in route.methods}
    assert actual == declared


def test_missing_source_tamper_and_night_gap(client, monkeypatch, tmp_path):
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)
    raw = tmp_path / "raw"
    raw.mkdir()
    content = (
        b"Datetime,SA_TEMP,SF_SPD_DM,CHWC_VLV_DM\n"
        b"2018-01-01 22:00:00,50,1,1.5\n"
        b"2018-01-02 07:00:00,,0,0\n"
        b"2018-01-02 07:02:00,54,1,0\n"
    )
    path = raw / "slice.csv"
    source = {"path": path.name, "sha256": hashlib.sha256(content).hexdigest(), "archive_member": path.name}
    monkeypatch.setattr(runtime, "SOURCES", {"slice": source})
    params = {"dataset_id": "slice", "signal_ids": ["SA_TEMP", "SA_TEMPSPT"]}
    assert client.get("/api/v1/datasets").json()["items"][0]["availability"] == "MISSING_SOURCE"
    response = client.get("/api/v1/series", params=params)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MISSING_SOURCE"
    path.write_bytes(content)
    payload = client.get("/api/v1/series", params=params).json()
    validate_schema(payload, "RuntimeSeries")
    assert payload["gap_before"] == [False, True, True]
    second_page = client.get("/api/v1/series", params={
        **params, "start": payload["timestamps"][1], "limit": 1,
    }).json()
    assert second_page["gap_before"] == [True]
    assert payload["signals"][0]["values"][1] is None
    assert payload["signals"][1] == {"canonical_id": "SA_TEMPSPT", "availability": "UNAVAILABLE",
                                     "value_status": "AS_DOCUMENTED", "warning_code": None, "values": [None] * 3}
    empty = client.get("/api/v1/series", params={**params, "start": "2026-01-01T00:00:00"}).json()
    assert empty["timestamps"] == [] and empty["next_start"] is None
    outcome = client.get("/api/v1/diagnostics", params={"dataset_id": "slice", "at": payload["timestamps"][0]})
    assert outcome.status_code == 200
    outcome = outcome.json()
    validate_schema(outcome, "RuntimeDiagnostics")
    assert outcome["anomaly_status"] == "DETECTED"
    assert outcome["cause_status"] == "NOT_ASSESSED"
    assert outcome["methods"][0]["predicate"] == "VIOLATED"
    assert outcome["methods"][1]["method_status"] == "INAPPLICABLE"
    assert outcome["methods"][2]["method_status"] == "INAPPLICABLE"
    assert {root["canonical_id"] for root in outcome["methods"][0]["roots"]} == {"SF_SPD_DM", "CHWC_VLV_DM"}
    path.write_bytes(content.replace(b"1.5", b"1.0"))
    response = client.get("/api/v1/series", params=params)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SOURCE_INTEGRITY"


@pytest.mark.parametrize(("rows", "code"), [
    (["2018-01-01 00:00:00", "not-a-timestamp"], "INVALID_TIMESTAMP"),
    (["2018-01-01 00:00:00", "2018-01-01 00:00:00"], "DUPLICATE_TIMESTAMP"),
    (["2018-01-01 00:01:00", "2018-01-01 00:00:00"], "OUT_OF_ORDER_TIMESTAMP"),
])
def test_invalid_import_does_not_write(client, rows, code):
    content = ("Datetime,SA_TEMP\n" + "".join(f"{row},32\n" for row in rows)).encode()
    before = set(settings.data_dir.glob("*/*"))
    result = client.post("/api/datasets/import", files={"file": ("invalid.csv", content)})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == code
    assert set(settings.data_dir.glob("*/*")) == before
    with SessionLocal() as session:
        assert session.query(Dataset).filter_by(sha256=hashlib.sha256(content).hexdigest()).first() is None


def test_concurrent_import_publishes_one_dataset(client):
    import uuid

    content = f"Datetime,SA_TEMP\n2018-01-01 00:00:00,{uuid.uuid4().int}\n".encode()
    def upload(_):
        return client.post("/api/datasets/import", files={"file": ("concurrent.csv", content)})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(upload, range(2)))
    assert [item.status_code for item in results] == [200, 200]
    payloads = [item.json() for item in results]
    assert {item["status"] for item in payloads} == {"SUCCESS", "DUPLICATE_SKIPPED"}
    assert len({item["dataset_id"] for item in payloads}) == 1


def test_import_rolls_back_if_file_publish_fails(monkeypatch):
    import uuid

    content = f"Datetime,SA_TEMP\n2018-01-01 00:00:00,{uuid.uuid4().int}\n".encode()
    from backend.app.services.import_service import ImportService
    from io import BytesIO

    publish = Path.hardlink_to
    def fail_raw(path, target):
        if path.parent.name == "raw":
            raise OSError("raw publication failed")
        return publish(path, target)

    before = set(settings.data_dir.glob("*/*"))
    with SessionLocal() as session:
        monkeypatch.setattr(Path, "hardlink_to", fail_raw)
        with pytest.raises(OSError, match="raw publication failed"):
            ImportService.process_csv_file(session, BytesIO(content), "rollback.csv")
        assert session.query(Dataset).filter_by(sha256=hashlib.sha256(content).hexdigest()).first() is None
        assert set(settings.data_dir.glob("*/*")) == before
        monkeypatch.setattr(Path, "hardlink_to", publish)
        assert ImportService.process_csv_file(session, BytesIO(content), "rollback.csv")["status"] == "SUCCESS"


def test_audit_guard_blocks_source_writes_and_external_sqlite():
    import os
    import sqlite3

    protected = Path(os.environ["BUILDINGPULSE_PROTECTED_ROOTS"].split(os.pathsep)[0])
    with pytest.raises(RuntimeError, match="Write to protected audit source"):
        (protected / "g01-guard-probe").open("wb")
    with pytest.raises(RuntimeError, match="outside audit scratch"):
        sqlite3.connect(protected / "buildingpulse.db")


def test_official_pressure_is_raw_and_units_unverified(client):
    key = "ds_8e5b1ddfdd14"
    pressures = {"SA_SP": 402.07953, "SA_SPSPT": 1.60746}
    response = client.get(f"/api/v1/datasets/{key}/signals")
    catalog = {item["canonical_id"]: item for item in response.json()["items"]}
    response = client.get("/api/v1/series", params={
        "dataset_id": key, "signal_ids": list(pressures), "limit": 1,
    })
    assert response.json()["timestamps"] == ["2018-01-01T01:00:00"]
    for signal in response.json()["signals"]:
        name = signal["canonical_id"]
        assert signal["values"] == [pressures[name]]
        assert signal.get("value_status") == "UNVERIFIED_UNIT"
        assert catalog[name]["value_status"] == "UNVERIFIED_UNIT"
        assert catalog[name]["unit"] is None and catalog[name]["source_unit"] is None
        assert catalog[name]["warning_code"] == "SEMANTICS_UNVERIFIED"


@pytest.mark.parametrize(("fan", "command", "anomaly", "cause", "issue", "reason"), [
    (0, 1.5, "UNASSESSED", "NOT_ASSESSED", None, "FAN_OFF"),
    (0.5, 1.5, "UNASSESSED", "NOT_ASSESSED", None, "FAN_STATUS_INVALID"),
    (1, None, "UNASSESSED", "NOT_ASSESSED", None, "COMMAND_VALUE_INVALID"),
    (1, 1.0, "NOT_DETECTED_IN_EVALUATED_TESTS", "NOT_ASSESSED", None, "COMMAND_FRACTION_RANGE"),
    (1, 1.5, "DETECTED", "NOT_ASSESSED", "SIGNAL_RANGE_VIOLATION", "COMMAND_FRACTION_RANGE"),
])
def test_range_check_has_signal_only_semantics(fan, command, anomaly, cause, issue, reason):
    outcome = runtime.evaluate_point({"sha256": "a" * 64},
                                     {"SF_SPD_DM": fan, "CHWC_VLV_DM": command},
                                     "2018-01-01T01:00:00", "BASIC")
    validate_schema(outcome, "RuntimeDiagnostics")
    assert outcome["anomaly_status"] == anomaly
    assert outcome["cause_status"] == cause
    assert outcome["issue_class"] == issue
    assert outcome["methods"][0]["reason_code"] == reason


def test_annual_catalog_and_indexed_seek(client, monkeypatch):
    items = client.get("/api/v1/datasets").json()["items"]
    annual = [item for item in items if item["name"] == "AHU_annual.csv"]
    assert {(item["rows"], item["is_full_year"], item["last"]) for item in annual} == {
        (10080, False, "2018-01-08T00:59:00"), (20160, False, "2018-01-15T00:59:00"),
        (525540, True, "2018-12-31T23:59:00"),
    }
    assert {item["first"] for item in annual} == {"2018-01-01T01:00:00"}
    validate_schema({"items": annual}, "RuntimeDatasetList")
    source = next(item for item in annual if item["is_full_year"])
    dataset_id = source["dataset_id"]

    def reject_csv(*_):
        pytest.fail("Annual query unexpectedly loaded the raw CSV into memory")

    monkeypatch.setattr(runtime, "read_verified", reject_csv)
    params = {"dataset_id": dataset_id, "signal_ids": "SA_SP"}
    end = client.get("/api/v1/series", params={**params, "start": source["last"], "limit": 1})
    validate_schema(end.json(), "RuntimeSeries")
    assert end.json()["timestamps"] == [source["last"]]
    assert end.json()["next_start"] is None
    assert end.json()["gap_before"] == [False]
    assert end.json()["signals"][0]["values"] == [401.8638]

    boundary = client.get("/api/v1/series", params={
        **params, "start": "2018-01-02T11:07:00", "limit": 2,
    }).json()
    assert boundary["timestamps"] == ["2018-01-02T11:07:00", "2018-01-02T11:08:00"]
    assert boundary["gap_before"] == [False, False]
    assert boundary["next_start"] == "2018-01-02T11:09:00"
    assert client.get("/api/v1/diagnostics", params={
        "dataset_id": dataset_id, "at": "2018-12-31T23:59:01",
    }).status_code == 404


@pytest.mark.parametrize(("part", "code"), [("raw", "SOURCE_INTEGRITY"), ("processed", "SOURCE_INTEGRITY")])
def test_annual_requires_matching_raw_and_parquet(client, monkeypatch, tmp_path, part, code):
    import shutil

    source = runtime.SOURCES["ds_8e5b1ddfdd14"]
    for name in ("raw", "processed"):
        (tmp_path / name).mkdir()
    raw = Path("raw") / source["path"]
    derived = Path(source["parquet_derivation"]["path"])
    for path in (raw, derived):
        shutil.copyfile(runtime.settings.data_dir / path, tmp_path / path)
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)
    params = {"dataset_id": "ds_8e5b1ddfdd14", "signal_ids": "SA_SP", "limit": 1}
    assert client.get("/api/v1/series", params=params).status_code == 200
    target = raw if part == "raw" else derived
    with (tmp_path / target).open("ab") as stream:
        stream.write(b"tamper")
    response = client.get("/api/v1/series", params=params)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == code


def test_annual_without_parquet_reads_bounded_legacy_csv(client, monkeypatch, tmp_path):
    import shutil

    source = runtime.SOURCES["ds_8e5b1ddfdd14"]
    (tmp_path / "raw").mkdir()
    shutil.copyfile(runtime.source_path(source), tmp_path / "raw" / source["path"])
    monkeypatch.setattr(runtime.settings, "DATA_ROOT", tmp_path)

    def reject_full_csv(*_):
        pytest.fail("Fallback loaded the annual CSV into memory")

    monkeypatch.setattr(runtime, "read_verified", reject_full_csv)
    params = {"dataset_id": "ds_8e5b1ddfdd14", "signal_ids": "SA_SP", "limit": 2}
    result = client.get("/api/v1/series", params={**params, "start": "2018-01-02T11:07:00"})
    assert result.status_code == 200
    validate_schema(result.json(), "RuntimeSeries")
    assert result.json()["timestamps"] == ["2018-01-02T11:07:00", "2018-01-02T11:08:00"]
    assert result.json()["gap_before"] == [False, False]
    assert result.json()["next_start"] == "2018-01-02T11:09:00"
