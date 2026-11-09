"""Aggregate future coordinator-coded answers. Review and QA exports never count."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from statistics import median

from research.study.build import PANEL, PROTOCOL

DIMENSIONS = ("eligibility", "temporal", "cause_limit", "action_evidence")


def score(assignments, responses, ratings):
    expected = {
        (person["participant_id"], visit["case_id"], visit["condition"])
        for person in assignments for visit in person["visits"]
    }
    results = defaultdict(Counter)
    elapsed = defaultdict(list)
    paired = defaultdict(lambda: defaultdict(Counter))
    for participant, case, arm in expected:
        results[arm]["assigned"] += 1
        paired[participant][arm]["assigned"] += 1

    excluded = 0
    seen, seen_ids, rated = set(), set(), set()
    for item in responses:
        if item["collection_mode"] in ("QA_ONLY", "REVIEW_ONLY"):
            excluded += 1
            continue
        if item["collection_mode"] != "PILOT" or (item["protocol"], item["panel_version"]) != (PROTOCOL, PANEL):
            raise ValueError("Unexpected collection mode or version")
        arm = item["condition"]
        key = item["participant_id"], item["case_id"], arm
        rid = item["response_id"]
        if key not in expected or key in seen or rid in seen_ids:
            raise ValueError("Missing assignment or duplicate response")
        seen.add(key)
        seen_ids.add(rid)
        if item["status"] not in ("COMPLETE", "TIMEOUT", "TECHNICAL_FAILURE"):
            raise ValueError("Unknown response status")
        results[arm][item["status"].lower()] += 1
        if item["status"] != "COMPLETE":
            continue
        if not 0 <= item["elapsed_ms"] <= 180000:
            raise ValueError("Invalid completed response time")
        values = ratings[rid]
        if set(values) != {*DIMENSIONS, "false_cause"} or not all(value in (0, 1) for value in values.values()):
            raise ValueError("Expected four adjudicated scores and false-cause flag")
        rated.add(rid)
        complete = int(all(values[dimension] for dimension in DIMENSIONS))
        results[arm]["all_four"] += complete
        results[arm].update(values)
        elapsed[arm].append(item["elapsed_ms"])
        paired[key[0]][arm]["all_four"] += complete
    if set(ratings) != rated:
        raise ValueError("Ratings contain unmatched or excluded records")
    for arm, counts in results.items():
        counts["no_export"] = counts["assigned"] - sum(counts[k] for k in ("complete", "timeout", "technical_failure"))
    contrasts = {
        person: arms["C"]["all_four"] / arms["C"]["assigned"] - arms["B"]["all_four"] / arms["B"]["assigned"]
        for person, arms in paired.items()
        if arms["C"]["assigned"] and arms["B"]["assigned"]
    } if seen else {}
    return {"evaluation": "DESCRIPTIVE_PILOT" if seen else "NOT_EXECUTED", "excluded_qa_or_review": excluded,
            "arms": dict(results), "completed_time_median_ms": {arm: median(times) for arm, times in elapsed.items()},
            "participant_contrast_c_minus_b_assigned": contrasts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assignments", type=Path)
    parser.add_argument("responses", type=Path, help="JSONL, pseudonym joined by coordinator for PILOT")
    parser.add_argument("ratings", type=Path)
    args = parser.parse_args()
    assignments = json.loads(args.assignments.read_text())
    responses = [json.loads(line) for line in args.responses.read_text().splitlines() if line.strip()]
    ratings = {}
    with args.ratings.open(newline="") as stream:
        for row in csv.DictReader(stream):
            rid = row.pop("response_id")
            if rid in ratings:
                raise ValueError("Duplicate adjudication")
            ratings[rid] = {key: int(value) for key, value in row.items()}
    print(json.dumps(score(assignments, responses, ratings), indent=2))
