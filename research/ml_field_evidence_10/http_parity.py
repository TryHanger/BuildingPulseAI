"""Compare baseline and updated HTTP apps with the same isolated fixtures."""
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

FIELD = "/api/research/field-evidence"


def http(base, path, body=None):
    request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.read()


def check(before, after, contract):
    guard = {
        "active_setpoint": "55.184006", "setpoint_exact": True, "temperature_unit": "degF",
        "physical_roles_verified": True, "origin": "VERIFIED_BAS", "control_mode": "RUNNING_WARM",
        "features": {"MA_TEMP": 70, "OA_TEMP": 72, "RA_TEMP": 73},
    }
    cases = (
        ("/api/v1/openapi.json", None),
        ("/api/v1/incidents?dataset_id=ds_8e5b1ddfdd14&start=2018-01-02T11%3A08%3A00&limit=1", None),
        ("/api/research/domain-shift-07", None),
        ("/api/research/domain-shift-07/applicability", guard),
        ("/api/research/domain-shift-07/applicability", {**guard, "active_setpoint": "53"}),
        ("/api/research/domain-shift-07/applicability", {**guard, "active_setpoint": None}),
        ("/api/research/virtual-sensors", None),
        ("/api/research/virtual-sensors/day?case=healthy&day=2018-10-20", None),
        ("/api/ml/models", None),
    )
    for path, body in cases:
        original = http(before, path, body)
        updated = http(after, path, body)
        assert original == updated and updated[0] == 200, (path, original[0], updated[0])
        if path.endswith("/applicability"):
            result = json.loads(updated[1])
            assert not result["inference_authorized"] and not result["incident_eligible"]
        if path == "/api/research/virtual-sensors":
            assert json.loads(updated[1])["use"] == "RESEARCH_ONLY"
        if "/incidents?" in path:
            assert "MODEL_ANOMALY" not in updated[1].decode()
        print("PASS byte-identical", "POST" if body else "GET", path, "HTTP", updated[0])

    old_status, old_document = http(before, "/openapi.json")
    new_status, new_document = http(after, "/openapi.json")
    assert old_status == new_status == 200
    old = json.loads(old_document)
    new = json.loads(new_document)
    additions = new["paths"].pop(FIELD)
    assert set(additions) == {"get"}
    new_schemas = new["components"]["schemas"]
    added_schemas = {name: new_schemas.pop(name) for name in sorted(new_schemas.keys() - old["components"]["schemas"].keys())}
    assert set(added_schemas) == {"FieldEvidence", "EvidenceWindow", "Observation", "Provenance", "SourceFile"}
    assert new == old
    assert http(before, FIELD)[0] == 404 and http(after, FIELD)[0] == 200
    contract.write_text(json.dumps({
        "openapi": new["openapi"],
        "info": {"title": "BuildingPulse Stage10 research field evidence", "version": "1.0.0"},
        "paths": {FIELD: additions},
        "components": {"schemas": added_schemas},
    }, ensure_ascii=False, indent=2) + "\n")
    print("PASS additive full OpenAPI diff: one research GET and five schemas. Diagnostic OpenAPI is byte-identical.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("contract", type=Path)
    check(**vars(parser.parse_args()))
