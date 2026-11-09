"""Exercise the v1 contract against a running FastAPI over HTTP."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from contracts.evidence_v1 import OPENAPI, validate_schema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8050")
    parser.add_argument("--output", type=Path, default=Path("handoff/http"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def get(path, schema, artifact=None, **query):
        suffix = f"?{urlencode(query, doseq=True)}" if query else ""
        with urlopen(f"{args.url}/api/v1{path}{suffix}", timeout=10) as response:
            print(f"GET {response.url} {response.status}")
            payload = json.load(response)
        if schema:
            validate_schema(payload, schema)
        if artifact:
            (args.output / f"{artifact}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            )
        return payload

    assert get("/openapi.json", None) == OPENAPI
    catalog = get("/datasets", "RuntimeDatasetList", "datasets")
    source = next(item for item in catalog["items"] if item["name"] == "AHU_annual.csv")
    dataset_id = source["dataset_id"]
    get(f"/datasets/{quote(dataset_id)}/signals", "RuntimeSignalList", "signals")
    series = get("/series", "RuntimeSeries", "series", dataset_id=dataset_id,
                 signal_ids=["SA_TEMP", "CHWC_VLV_DM"], limit=3)
    off = get("/diagnostics", "RuntimeDiagnostics", "diagnostics",
              dataset_id=dataset_id, at=series["timestamps"][0])
    assert off["mode"] == "OFF" and off["display_state"] == "NOT_EVALUABLE"
    start = None
    while True:
        query = {"start": start} if start is not None else {}
        fan = get("/series", "RuntimeSeries", dataset_id=dataset_id,
                  signal_ids="SF_SPD_DM", limit=1440, **query)
        timestamp = next((t for t, value in zip(fan["timestamps"], fan["signals"][0]["values"])
                          if value == 1), None)
        if timestamp is not None:
            break
        start = fan["next_start"]
        if start is None:
            raise AssertionError("The selected dataset contains no fan-on sample")
    on = get("/diagnostics", "RuntimeDiagnostics", "diagnostics-fan-on", dataset_id=dataset_id, at=timestamp)
    assert on["fan_on"] is True and on["mode"] == "UNKNOWN"
    assert on["methods"][0]["method_status"] == "APPLICABLE"
    assert on["cause_status"] == "NOT_ASSESSED" and on["model_status"] == "UNAVAILABLE"
    annual = next(item for item in catalog["items"] if item["is_full_year"])
    full_id = annual["dataset_id"]
    pressure = get("/series", "RuntimeSeries", "official-first-pressure", dataset_id=full_id,
                   signal_ids=["SA_SP", "SA_SPSPT"], limit=1)
    assert [item["values"][0] for item in pressure["signals"]] == [402.07953, 1.60746]
    assert all(item["value_status"] == "UNVERIFIED_UNIT" for item in pressure["signals"])
    end = get("/series", "RuntimeSeries", "annual-last", dataset_id=full_id, start=annual["last"],
              signal_ids="SA_SP", limit=1)
    assert end["timestamps"] == ["2018-12-31T23:59:00"] and end["next_start"] is None
    saturated = get("/diagnostics", "RuntimeDiagnostics", "valid-saturated-command",
                    dataset_id=full_id, at="2018-01-09T06:02:00")
    assert saturated["anomaly_status"] == "NOT_DETECTED_IN_EVALUATED_TESTS"
    assert saturated["cause_status"] == "NOT_ASSESSED" and saturated["issue_class"] is None
    print("PASS schema validation, real fan-off, fan-on, pressure, year end and valid saturation")


if __name__ == "__main__":
    main()
