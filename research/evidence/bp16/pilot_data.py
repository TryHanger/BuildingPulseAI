"""Facilitator-only allocation and offline scoring for BP-16."""
import argparse
import json
import random
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[3]
SCHEDULE = json.loads((ROOT / "frontend/src/pilot/schedule.json").read_text())
PROTOCOL = "bp16-pilot-v1"
BASELINE = "ab99ff28c99be9fc93e4fab6abc2748e2b7fd904"
KEY = {
    # Decision, justified abstention, next measurement, unsupported inference choices.
    "A": (2, 3, 1, {1, 2}),
    "B": (4, 1, 3, {2, 3}),
    "C": (1, 4, 2, {1, 2, 3}),
    "D": (3, 2, 4, {1, 3, 4}),
}
ANOMALY = {
    "A": "MODEL_ANOMALY",
    "B": "ABSTAIN",
    "C": "BAS_ON_TO_OFF_OBSERVED",
    "D": "ABSTAIN",
}
QUESTIONS = {"decision", "inference", "measurement"}
SESSION_FIELDS = {"protocol", "baseline", "session_id", "sequence", "responses"}
RESPONSE_FIELDS = {"case_id", "condition", "position", "anomaly", "choices", "elapsed_ms", "interrupted"}


def assignments(blocks, seed):
    if blocks < 1:
        raise ValueError("expected at least one block")
    rng = random.Random(seed)
    return [rng.sample(range(1, 9), 8) for _ in range(blocks)]


def tasks(sequence):
    if type(sequence) is not int or not 1 <= sequence <= 8:
        raise ValueError("invalid sequence")
    orders = SCHEDULE["orders"][(sequence - 1) // 2]
    conditions = SCHEDULE["conditions"][(sequence - 1) % 2]
    return list(zip(orders, conditions, strict=True))


def score(record):
    if not isinstance(record, dict) or set(record) != SESSION_FIELDS:
        raise ValueError("unexpected session fields")
    if record["protocol"] != PROTOCOL or record["baseline"] != BASELINE:
        raise ValueError("unknown protocol or baseline")
    session_id = record["session_id"]
    if not isinstance(session_id, str) or str(UUID(session_id, version=4)) != session_id:
        raise ValueError("invalid random session ID")
    expected = tasks(record["sequence"])
    responses = record["responses"]
    if not isinstance(responses, list) or len(responses) != len(expected):
        raise ValueError("expected all four responses")

    scored = []
    for position, ((case, condition), response) in enumerate(zip(expected, responses, strict=True), 1):
        if not isinstance(response, dict) or set(response) != RESPONSE_FIELDS:
            raise ValueError("unexpected response fields")
        if (response["case_id"] != case or response["condition"] != condition or
                type(response["position"]) is not int or response["position"] != position or
                response["anomaly"] != ANOMALY[case]):
            raise ValueError("stimulus differs from the assigned BP-15 case")
        elapsed = response["elapsed_ms"]
        interrupted = response["interrupted"]
        if type(elapsed) is not int or elapsed < 0 or type(interrupted) is not bool:
            raise ValueError("invalid timer record")
        choices = response["choices"]
        if (not isinstance(choices, dict) or set(choices) != QUESTIONS or
                any(type(value) is not int or not 1 <= value <= 4 for value in choices.values())):
            raise ValueError("invalid answer codes")

        decision, inference, measurement, unsupported = KEY[case]
        scored.append({
            "case_id": case,
            "condition": condition,
            "position": position,
            "correct_decision": choices["decision"] == decision,
            "unsupported_inference": choices["inference"] in unsupported,
            "justified_abstention": choices["inference"] == inference,
            "correct_measurement": choices["measurement"] == measurement,
            "elapsed_ms": elapsed,
            "include_in_timing_summary": not interrupted,
        })

    totals = {condition: sum(row["correct_decision"] for row in scored if row["condition"] == condition)
              for condition in ("signal-only", "evidence-to-action")}
    return {
        "session_id": session_id,
        "sequence": record["sequence"],
        "evidence_minus_signal_decision_accuracy": (totals["evidence-to-action"] - totals["signal-only"]) / 2,
        "tasks": scored,
    }


def score_files(paths):
    results = [score(json.loads(path.read_text())) for path in paths]
    if len({result["session_id"] for result in results}) != len(results):
        raise ValueError("duplicate anonymous session")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    assign = commands.add_parser("assign")
    assign.add_argument("--blocks", type=int, required=True)
    assign.add_argument("--seed", type=int, required=True)
    scoring = commands.add_parser("score")
    scoring.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        output = assignments(args.blocks, args.seed) if args.command == "assign" else score_files(args.files)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
