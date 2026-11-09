"""Check accepted package bytes, historical OpenAPI diff and live Stage10 route alone."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient

FIELD = "/api/research/field-evidence"
FROZEN = "cfd6df405d4e99324457a9cfa744e6c5bd4d994b21b9a87f10dd5f43f45726b9"


def check_archive(path):
    with ZipFile(path) as z:
        assert z.testzip() is None
        hashes = [line.split("  ", 1) for line in z.read("SHA256SUMS").decode().splitlines()]
        members = {path.removeprefix("./") for _, path in hashes}
        assert len(members) == len(hashes)
        assert members == {name for name in z.namelist() if not name.endswith("/")} - {"SHA256SUMS"}
        for expected, name in hashes:
            assert sha256(z.read(name.removeprefix("./"))).hexdigest() == expected
    print(f"PASS {path.name}: {len(hashes)} payload hashes")


def check_stage10(archive, workspace):
    with ZipFile(archive) as z, TemporaryDirectory() as root:
        accepted = json.loads(z.read("evidence/openapi-18060.json"))
        historical = json.loads(z.read("evidence/openapi-18059.json"))
        added = accepted["paths"].pop(FIELD)
        assert set(added) == {"get"}
        new_schemas = accepted["components"]["schemas"]
        previous = historical["components"]["schemas"]
        for key in new_schemas.keys() - previous.keys():
            del new_schemas[key]
        assert accepted == historical
        assert not any("replication" in key or "stage13" in key for key in accepted["paths"])
        print("PASS archived OpenAPI difference is isolated to the Stage10 research route and schemas")

        source = Path(root) / "endpoint.py"
        source.write_bytes(z.read("overlay/backend/app/api/endpoints/field_evidence.py"))
        bundle = Path(root) / "frozen.json"
        payload = z.read("frozen-data/field_evidence_10.json")
        bundle.write_bytes(payload)
        spec = importlib.util.spec_from_file_location("audited_field_evidence", source)
        endpoint = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(endpoint)
        assert endpoint.BUNDLE_SHA256 == sha256(payload).hexdigest() == FROZEN
        endpoint.BUNDLE = bundle
        app = FastAPI()
        app.include_router(endpoint.router, prefix="/api")
        with TestClient(app) as client:
            response = client.get(FIELD)
            assert response.status_code == 200 and response.content == payload
            assert response.headers["Cache-Control"] == "no-store"
            assert len(endpoint.FieldEvidence.model_validate_json(payload, strict=True).cases) == 12
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                assert client.request(method, FIELD).status_code == 405
            assert client.get(FIELD, params={"path": "/etc/passwd"}).status_code == 422
            bundle.write_bytes(b"tampered")
            assert client.get(FIELD).json() == {"detail": "SOURCE_PROVENANCE_UNVERIFIED"}
            bundle.unlink()
            assert client.get(FIELD).status_code == 503
        print("PASS live standalone Stage10 endpoint: 12 cases, frozen payload, GET only, fail closed")

        manifest = [line.split("  ", 1) for line in z.read("evidence/accepted-base.sha256").decode().splitlines()]
        missing, mismatch = [], []
        for expected, path in manifest:
            file = workspace / path
            if not file.is_file():
                missing.append(path)
            elif sha256(file.read_bytes()).hexdigest() != expected:
                mismatch.append(path)
        print(f"Accepted Stage09 base in local export: {len(manifest)} paths, "
              f"{len(missing)} missing and {len(mismatch)} mismatched.")
        if missing or mismatch:
            print("Full integrated Stage10/FDD HTTP and model-runtime regression unavailable on this base.")
            print("Examples missing:", *missing[:5])
            print("Examples mismatched:", *mismatch[:5])


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("workspace", type=Path)
    args = cli.parse_args()
    archives = {n: args.workspace / f"BUILDINGPULSE_BP_ML_FIELD_{name}_REVIEW.zip" for n, name in
                [(9, "NATIVE_09"), (10, "EVIDENCE_10"), (11, "MECHANISM_11"), (12, "OBSERVATIONAL_12")]}
    for path in archives.values():
        check_archive(path)
    check_stage10(archives[10], args.workspace)
