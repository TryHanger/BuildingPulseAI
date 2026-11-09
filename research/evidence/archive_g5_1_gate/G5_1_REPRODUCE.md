# G5.1 reproduction and source receipts

Apply `overlay/` to the accepted G4.1/G5 tree. `MANIFEST.json` records baseline and replacement hashes. `SHA256SUMS.txt` covers every payload. Large telemetry and prior ZIPs are omitted.

## Inputs

Project root on the audited machine is `/mnt/c/Users/Nikita/Desktop/BuildingPulseAi`. The following project-relative paths are also present inside the RC2 snapshot and were read from its restored copy.

| Path | SHA-256 |
|---|---|
| `data/raw/csiro_ahu9.parquet` | `d43028c46d6fadbed7f2deb749626f78be277573ead1e8b1abe8babd7515db6d` |
| `data/raw/csiro_ahu10.parquet` | `f789b7efc5a0ec9857d5126137f727b94ad0895b63ff9b2170dd5651b26d3610` |
| `data/raw/csiro_fault_experiments.parquet` | `b7ebad8a25baa8da7740186eb52a1eb62d0602c82dcc394ed0527ea5c6fd65f2` |

CSIRO commit `3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6` is pinned. The source of `join_ground_truth` has SHA-256 `c23f7c0a824601889149fea46a96b838c6c7f2eb714c2919ee05cccc9d303ab3`. The implementation uses the same AHU key and start-inclusive/end-exclusive native timestamps. It validates counts per source row independently with SQLite in memory. It does not write the publisher's combined table or mix labels into telemetry. [Publisher code](https://github.com/csiro-energy-systems/ahu-fault-detection-dataset/blob/3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6/src/hvac_fdd_dataset/data_wrangling.py), [publisher README](https://github.com/csiro-energy-systems/ahu-fault-detection-dataset/blob/3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6/README.md)

`outputs/PREVIOUSLY_REVIEWED_DAYS.txt` is the sorted set of date prefixes from the `timestamp` column in `research/runs/csiro_ahu10_pointwise_predictions.csv` inside `BUILDINGPULSE_AUDIT_STAGE_8C_RELEASE_CANDIDATE.zip` (actual archive SHA-256 `7af1ae34122daec1a2fa906a060e5d2e7b9e5ac10c86f17530edcd9e8703eb7e`). Only timestamps were used. This is a lower bound on exposure. The facility remains retrospective. The CSV derivatives in this package retain CSIRO attribution and CC BY-SA 4.0 data terms. [CSIRO data license](https://github.com/csiro-energy-systems/ahu-fault-detection-dataset/blob/3eb50a9ce1d4eeed778877cbfdbd259d2298d8e6/README.md#license)

## Commands

Use the accepted backend and frontend dependencies and separate disposable SQLite and DATA_ROOT as in G5_REPRODUCE. Use read-only input copies for the source audit.

```bash
python research/g51/qualify_interventions.py data/raw /scratch/g51 \
  --reviewed-days /unpacked/outputs/PREVIOUSLY_REVIEWED_DAYS.txt
python -m pytest backend/tests contracts/test_evidence_v1.py tests -q
npm --prefix frontend run build
python contracts/check_fixture_types.py
```

With scratch FastAPI and Vite running, execute `PYTHONPATH=. python scripts/smoke_g01_http.py` and `python scripts/test_playwright_g4.py --output /scratch/browser`. The 10/11 boundary examples use `/api/v1/investigation?dataset_id=demo-g4-mat&start=2018-01-02T11:05:00&limit=10` and `limit=11`. The browser test changes only the query to select the real server window. The negative and contract tests cover missing inputs, gaps, ended unconfirmed runs and report hash reproduction. No training tools are called.
