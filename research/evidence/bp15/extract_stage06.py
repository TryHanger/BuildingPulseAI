"""Extract the predeclared BP-15 window from the accepted Stage06 review archive."""
import argparse
import csv
import gzip
import io
import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE_SHA = "64ce1a8c46e163ae346df4d3bfec82d486d3a0052fc5da47a4cd2112a45e6bcf"
TRACE = "TARGET_NORMAL_06_MINUTE_TRACE.csv.gz"
BLOCKS = "TARGET_NORMAL_06_BLOCKS.csv"
RECEIPT = "TARGET_NORMAL_06_RECEIPT.json"
STAGE06 = ROOT / "research/evidence/archive_bp_ml_transfer_normal_06"
ACCEPTED_TRACE = Path(__file__).resolve().parent / "accepted" / TRACE


def verified(payload, expected):
    if sha256(payload).hexdigest() != expected:
        raise ValueError("Stage06 checksum mismatch")
    return payload


def extract(archive):
    receipt_bytes = (STAGE06 / RECEIPT).read_bytes()
    receipt = json.loads(receipt_bytes)
    trace = ACCEPTED_TRACE.read_bytes()
    block_bytes = (STAGE06 / BLOCKS).read_bytes()
    if archive:
        with ZipFile(io.BytesIO(verified(archive.read_bytes(), ARCHIVE_SHA))) as bundle:
            if any(bundle.read(name) != payload for name, payload in (
                (RECEIPT, receipt_bytes), (TRACE, trace), (BLOCKS, block_bytes)
            )):
                raise ValueError("Stage06 archive differs from accepted repository copies")
    trace = verified(trace, receipt["artifacts"][TRACE])
    block_bytes = verified(block_bytes, receipt["artifacts"][BLOCKS])
    rows = csv.DictReader(io.StringIO(gzip.decompress(trace).decode()))
    points = []
    for row in rows:
        second = int(row["model_seconds"])
        if not 17645700 <= second < 17649300:
            continue
        prediction = row["LIGHTGBM_SOURCE_TRAINED_PREDICTION_degF"]
        points.append({
            "model_seconds": second,
            "source_row": int(row["csv_row_1based"]),
            "sat_deg_f": float(row["SAT_MEASURED_SIMULATED_BAS_degF"]),
            "setpoint_deg_f": float(row["ACTIVE_SAT_SETPOINT_degF"]),
            "prediction_deg_f": float(prediction) if prediction else None,
            "fan_status": float(row["FAN_STATUS"]),
            "plant_mode": int(row["PLANT_MODE"]),
            "source_support": row["SOURCE_SUPPORT"] == "True",
            "eligible": row["ELIGIBLE"] == "True",
            "abstain_reason": row["ABSTAIN_REASON"] or None,
        })
    if [p["model_seconds"] for p in points] != list(range(17645700, 17649300, 60)):
        raise ValueError("Unexpected Stage06 clock or window")
    blocks = [
        {
            "block": int(row["block"]),
            "start_model_s": int(row["start_model_s"]),
            "end_exclusive_model_s": int(row["end_exclusive_model_s"]),
            "eligible_minutes": int(row["eligible_minutes"]),
            "z": float(row["lightgbm_reduced_z"]),
            "decision": row["lightgbm_reduced_decision"],
        }
        for row in csv.DictReader(io.StringIO(block_bytes.decode()))
    ]
    return {
        "provenance": {
            "archive_sha256": ARCHIVE_SHA,
            "trace_sha256": receipt["artifacts"][TRACE],
            "blocks_sha256": receipt["artifacts"][BLOCKS],
            "receipt_sha256": sha256(receipt_bytes).hexdigest(),
            "source_sha256": receipt["sha256"]["BaselineSystem.csv"],
            "model_sha256": receipt["sha256"]["REDUCED_SAT.lightgbm.txt"],
        },
        "clock": receipt["clock_basis"],
        "gate": receipt["gate"],
        "calendar_minutes": receipt["calendar_minutes"],
        "eligible_minutes": receipt["eligible_minutes"],
        "independent_normal_runs": receipt["independent_normal_runs"],
        "threshold": receipt["alarm_z"],
        "blocks": blocks,
        "points": points,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="also verify the original Stage06 review ZIP")
    args = parser.parse_args()
    print(json.dumps(extract(args.archive), indent=2, allow_nan=False, sort_keys=True))
