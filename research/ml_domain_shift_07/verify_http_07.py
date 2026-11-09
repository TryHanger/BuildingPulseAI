"""Check the live applicability endpoint and incident isolation with synthetic evidence."""
import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request(url, body=None):
    outgoing = Request(url, data=None if body is None else json.dumps(body).encode(),
                       headers={"Content-Type": "application/json"})
    try:
        with urlopen(outgoing, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def main(api):
    prefix = api + "/api/research/domain-shift-07"
    code, body = request(prefix)
    assert code == 200
    registry = json.loads(body)
    assert registry["transfer_normal_gate"] == "STOP_OOD_HEALTHY"
    assert registry["historical_normal_evidence"]["lightgbm_alarm_blocks"] == 7

    incidents = api + "/api/v1/incidents?" + urlencode({
        "dataset_id": "ds_8e5b1ddfdd14", "start": "2018-01-02T11:08:00", "limit": 1,
    })
    before = request(incidents)
    assert before[0] == 200
    base = {
        "active_setpoint": "55.184006", "setpoint_exact": True, "temperature_unit": "degF",
        "physical_roles_verified": True, "origin": "VERIFIED_BAS", "control_mode": "RUNNING_WARM",
        "features": {"MA_TEMP": 70, "OA_TEMP": 72, "RA_TEMP": 73},
    }
    for patch, expected in (
        ({}, "SOURCE_REGIME_MATCH_ONLY"),
        ({"active_setpoint": "53.2765195"}, "NOT_APPLICABLE_CONTROL_REGIME"),
        ({"active_setpoint": None}, "ABSTAIN_DOMAIN_SHIFT"),
    ):
        code, body = request(prefix + "/applicability", {**base, **patch})
        assert code == 200
        result = json.loads(body)
        assert result["status"] == expected and not any(
            result[key] for key in ("inference_authorized", "deployment_eligible", "incident_eligible"))
        assert request(incidents, result)[0] == 405
        print("PASS", result["status"], result["reason"])
    assert request(prefix + "/applicability", {**base, "True Valve Position": 0})[0] == 422
    assert request(incidents) == before
    print("PASS rejects oracle; existing FDD incident payload byte-identical after research requests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    main(parser.parse_args().api)
