import io
import pytest

def test_import_missing_time_column(client):
    csv_content = b"col_a,col_b\n1,2\n3,4\n"
    response = client.post(
        "/api/datasets/import",
        files={"file": ("invalid.csv", csv_content, "text/csv")},
        data={"source_kind": "USER_UPLOADED"}
    )
    assert response.status_code == 422
    assert "не найдена колонка даты/времени" in response.json()["detail"]

def test_import_empty_csv(client):
    csv_content = b""
    response = client.post(
        "/api/datasets/import",
        files={"file": ("empty.csv", csv_content, "text/csv")},
        data={"source_kind": "USER_UPLOADED"}
    )
    assert response.status_code == 400

def test_import_valid_fixture_and_idempotence(client):
    import uuid
    uid = uuid.uuid4().hex[:8]
    csv_data = (
        f"Datetime,OA_TEMP,RA_TEMP,MA_TEMP,SA_TEMP,CHWC_VLV_DM\n"
        f"2024-05-01 10:00:00,68.5,72.0,70.1,55.4,0.45\n"
        f"2024-05-01 10:01:00,68.7,72.1,70.2,55.3,0.46\n"
        f"2024-05-01 10:02:00,68.9,72.0,70.3,55.5,0.{int(uid, 16)}\n"
    ).encode("utf-8")

    response = client.post(
        "/api/datasets/import",
        files={"file": (f"fixture_{uid}.csv", csv_data, "text/csv")},
        data={
            "source_kind": "USER_UPLOADED",
            "source_fault_label": "TEST_GROUND_TRUTH"
        }
    )
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "SUCCESS"
    assert res_json["rows_count"] == 3
    assert "OA_TEMP" in res_json["mapped_channels"]
    assert "SA_TEMP" in res_json["mapped_channels"]

    # Re-upload same file: must be idempotent and return DUPLICATE_SKIPPED
    response_dup = client.post(
        "/api/datasets/import",
        files={"file": (f"fixture_{uid}.csv", csv_data, "text/csv")},
        data={"source_kind": "USER_UPLOADED"}
    )
    assert response_dup.status_code == 200
    dup_json = response_dup.json()
    assert dup_json["status"] == "DUPLICATE_SKIPPED"
    assert dup_json["dataset_id"] == res_json["dataset_id"]

def test_path_traversal_sanitization():
    from backend.app.services.import_service import ImportService
    bad_name = "../../../etc/passwd"
    clean = ImportService.sanitize_filename(bad_name)
    assert ".." not in clean
    assert "/" not in clean
    assert "\\" not in clean
