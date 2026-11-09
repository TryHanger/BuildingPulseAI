import copy
import json
from collections import Counter
from itertools import permutations
from uuid import uuid4

import pytest

from pilot_data import ANOMALY, BASELINE, PROTOCOL, assignments, score, score_files, tasks


def test_assignments_balance_cases_positions_and_interface_order():
    cases = "ABCD"
    conditions = ("signal-only", "evidence-to-action")
    schedules = [tasks(code) for code in range(1, 9)]
    assert all(sorted(case for case, _ in order) == list(cases) for order in schedules)
    assert all(Counter(condition for _, condition in order) == dict.fromkeys(conditions, 2) for order in schedules)
    for offset in range(4):
        assert Counter(order[offset] for order in schedules) == {(case, condition): 1 for case in cases for condition in conditions}
    assert Counter((left[0], right[0]) for order in schedules for left, right in zip(order, order[1:])) == {
        pair: 2 for pair in permutations(cases, 2)}
    transitions = Counter((left[1], right[1]) for order in schedules for left, right in zip(order, order[1:]))
    signal, evidence = conditions
    assert transitions[signal, evidence] == transitions[evidence, signal] == 8
    assert transitions[signal, signal] == transitions[evidence, evidence] == 4
    blocks = assignments(3, 1601)
    assert all(sorted(block) == list(range(1, 9)) for block in blocks)
    assert blocks == assignments(3, 1601)


@pytest.fixture
def contract_record():
    choices = {"A": (2, 3, 1), "B": (4, 1, 3), "C": (1, 4, 2), "D": (3, 2, 4)}
    return {
        "protocol": PROTOCOL, "baseline": BASELINE, "session_id": str(uuid4()), "sequence": 1,
        "responses": [
            {"case_id": case, "condition": condition, "position": position, "anomaly": ANOMALY[case],
             "elapsed_ms": 250, "interrupted": False,
             "choices": dict(zip(("decision", "inference", "measurement"), choices[case], strict=True))}
            for position, (case, condition) in enumerate(tasks(1), 1)
        ],
    }


def test_offline_scoring(contract_record):
    contract_record["responses"][1]["choices"] = {"decision": 1, "inference": 2, "measurement": 1}
    contract_record["responses"][1]["interrupted"] = True
    result = score(contract_record)
    assert result["evidence_minus_signal_decision_accuracy"] == -0.5
    assert [row["correct_decision"] for row in result["tasks"]] == [True, False, True, True]
    assert [row["justified_abstention"] for row in result["tasks"]] == [True, False, True, True]
    assert [row["unsupported_inference"] for row in result["tasks"]] == [False, True, False, False]
    assert [row["correct_measurement"] for row in result["tasks"]] == [True, False, True, True]
    assert [row["include_in_timing_summary"] for row in result["tasks"]] == [True, False, True, True]


@pytest.mark.parametrize("target,key,value", [
    ("session", "name", "example"),
    ("session", "baseline", "other"),
    ("session", "sequence", True),
    ("response", "anomaly", "FAULT"),
    ("response", "elapsed_ms", -1),
    ("response", "condition", "evidence-to-action"),
    ("response", "choices", {"decision": 1, "inference": 3, "measurement": True}),
])
def test_refuses_wrong_contract(contract_record, target, key, value):
    record = copy.deepcopy(contract_record)
    fields = record if target == "session" else record["responses"][0]
    fields[key] = value
    with pytest.raises(ValueError):
        score(record)


def test_duplicate_download_is_refused(contract_record, tmp_path):
    first, duplicate = tmp_path / "first.json", tmp_path / "duplicate.json"
    for path in (first, duplicate):
        path.write_text(json.dumps(contract_record))
    with pytest.raises(ValueError, match="duplicate"):
        score_files([first, duplicate])
