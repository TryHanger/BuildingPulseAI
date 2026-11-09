"""Run each point budget in a fresh process; ru_maxrss uses Linux KiB."""
import argparse
import json
import resource
from time import perf_counter

from fastapi.testclient import TestClient
from backend.app.main import app

parser = argparse.ArgumentParser()
parser.add_argument("limit", type=int, choices=(1, 50, 500, 1440))
parser.add_argument("--start", default="2018-12-29T12:00:00")
args = parser.parse_args()
params = {
    "dataset_id": "ds_8e5b1ddfdd14", "start": args.start, "limit": args.limit,
    "signal_ids": ["SA_SP", "SA_SPSPT", "SA_TEMP", "CHWC_VLV_DM", "SF_SPD_DM"],
}

def rss():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)

with TestClient(app) as client:
    baseline = rss()
    start = perf_counter()
    response = client.get("/api/v1/series", params=params)
    elapsed = perf_counter() - start
    peak = rss()
    response.raise_for_status()
    data = response.json()
    assert len(data["timestamps"]) == args.limit
    assert data["timestamps"][0] == args.start
    print(json.dumps({"limit": args.limit, "start": args.start, "elapsed_seconds": round(elapsed, 4),
                      "rss_baseline_mib": baseline, "rss_peak_mib": peak,
                      "rows": len(data["timestamps"]), "last": data["timestamps"][-1]}))
