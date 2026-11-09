"""Run inside the backend image against a disposable SQLite copy and read-only data."""
import json
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def get(path):
    with urlopen("http://127.0.0.1:8000" + path, timeout=10) as response:
        print("GET", path, response.status, flush=True)
        return json.load(response)


def main():
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1"])
    try:
        for attempt in range(80):
            try:
                health = get("/api/health")
                break
            except URLError:
                if server.poll() is not None or attempt == 79:
                    raise
                time.sleep(.25)
        assert health["database"] == "ok"
        assert get("/api/v1/openapi.json")["info"]["version"] == "1.0.0-rc.11"
        catalog = get("/api/v1/datasets")
        assert next(item for item in catalog["items"] if item["is_full_year"])["rows"] == 525540
        suffix = "?dataset_id=ds_8e5b1ddfdd14"
        series = get("/api/v1/series" + suffix + "&signal_ids=SA_SP&start=2018-12-31T23:59:00&limit=1")
        assert series["timestamps"] == ["2018-12-31T23:59:00"]
        assert series["signals"][0]["value_status"] == "UNVERIFIED_UNIT"
        diagnostics = get("/api/v1/diagnostics" + suffix + "&at=2018-12-31T23:59:00")
        assert diagnostics["cause_status"] == "NOT_ASSESSED"
        modes = get("/api/v1/modes" + suffix + "&start=2018-07-03T12:00:00&limit=1")
        assert modes["segments"][0]["mode"] == "RUNNING"
        assert modes["physical_context"]["mechanical_cooling_enable"] == "UNKNOWN"
        assert isinstance(get("/api/scenarios")["items"], list)
        incidents = get("/api/v1/incidents" + suffix + "&start=2018-01-02T11:08:00&limit=1440")
        assert incidents["coverage"]["evaluated"] > 0 and incidents["events"] == []
        assert incidents["rule"]["panel"] == "BASIC"
        lbnl = get("/api/v1/investigation" + suffix)
        assert lbnl["source_coverage"]["evaluated"] == 187192 and not lbnl["events"]
        demo = get("/api/v1/investigation?dataset_id=demo-g4-mat")
        assert demo["provenance"] == "DEMO_FIXTURE" and len(demo["events"]) == 1
        assert demo["events"][0]["sensor_root_count"] == 5 and demo["events"][0]["observation_count"] == 55
        print("PASS Docker isolated read-only v1, legacy listing and both G4 investigation paths")
        if "--g54" in sys.argv:
            week = get("/api/v1/g36-benchmark?dataset=g36-1wk&scenario=VALVE_CLOSED&start=17647920&limit=1")
            assert week["scope"] == "UNPAIRED_DESCRIPTIVE"
            assert (week["paired_causal_gate"], week["unpaired_descriptive_gate"], week["runs_per_scenario"]) == ("STOP", "PASS", 1)
            assert week["summaries"][0]["samples"] == 10081
            assert week["points"][0]["confirmed_start"] and week["points"][0]["reference_oracle"] is None
            tail = get("/api/v1/g36-benchmark?dataset=g36-1wk&scenario=VALVE_CLOSED&panel=EXTRA_SIMULATED&start=18230340&limit=2")
            assert [point["reference_oracle"] for point in tail["points"]] == [1, 1]
            assert all(point["source_oracle_status"] == "SOURCE_ORACLE_EXCEPTION" for point in tail["points"])
            print("PASS Docker G36-1wk BASIC and EXTRA")
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
