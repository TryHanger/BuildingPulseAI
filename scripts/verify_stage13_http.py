"""Verify the recovered Stage13 application against accepted Stage10 contracts."""
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def verify():
    root = Path(__file__).resolve().parents[1]
    accepted = root / "research/evidence/field_evidence_10/evidence/openapi-18060.json"
    with TestClient(app) as client:
        def read(url):
            response = client.get(url)
            assert response.status_code == 200, (url, response.status_code)
            print("PASS GET", url)
            return response

        assert read("/openapi.json").json() == json.loads(accepted.read_text())
        print("PASS complete OpenAPI matches accepted Stage10")
        content = read("/api/research/field-evidence").content
        assert sha256(content).hexdigest() == "cfd6df405d4e99324457a9cfa744e6c5bd4d994b21b9a87f10dd5f43f45726b9"
        incidents = read("/api/v1/incidents?dataset_id=ds_8e5b1ddfdd14&start=2018-01-02T11:08:00&limit=1").json()
        assert incidents["events"] == [] and incidents["coverage"]["samples"] == 1
        assert read("/api/research/virtual-sensors").json()["use"] == "RESEARCH_ONLY"
        assert read("/api/research/domain-shift-07").json()["deployment_eligible"] is False
        assert client.post("/api/research/field-evidence").status_code == 405


if __name__ == "__main__":
    verify()
