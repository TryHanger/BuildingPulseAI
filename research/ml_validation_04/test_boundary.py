"""The SAT archive cannot accept an external source or emit a field diagnosis."""
import pytest

from research.ml_repro_02.test_research import API, DATE, client, registry_dir, signature


@pytest.mark.parametrize("query", [
    [("dataset_id", "field-data")],
    [("method", "SYSTEM_MAX_8")],
    [("threshold", "2")],
    [("day", DATE)],
    [("case", "healthy")],
])
def test_archive_rejects_unknown_and_duplicate_parameters(client, query):
    response = client.get(API + "/day", params=[("case", "sa-plus-2"), ("day", DATE), *query])
    assert response.status_code == 422
    assert response.json()["detail"] == "ARCHIVE_CASE_AND_DAY_ONLY"


def test_archive_exposes_evidence_boundary(client):
    expected = {"cohort": "PREVIOUSLY_INSPECTED_SIMULATION",
                "external_validation": "BLOCKED_EXTERNAL_VALIDATION",
                "alarm_meaning": "MODEL_RESIDUAL_ONLY"}
    metadata = client.get(API).json()
    response = client.get(API + "/day", params={"case": "sa-plus-2", "day": DATE})
    assert response.status_code == 200
    day = response.json()
    assert metadata["evidence_boundary"] == day["metadata"]["evidence_boundary"] == expected
    assert day["method"] == "SAT_ONLY" and day["alert"] == "MODEL_ANOMALY"
    assert day["threshold"] == 3 and metadata["policy_version"] == "sat-daily-coverage@1.0.0"
