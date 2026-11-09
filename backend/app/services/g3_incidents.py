"""Read-only bounded windows over a verified sparse episode index."""
import hashlib
import json
from bisect import bisect_left
from datetime import datetime
from functools import lru_cache

from backend.app.services import investigator_v1 as runtime
from backend.app.services.g3_symptom import (
    INAPPLICABLE_CHECKS, POSSIBLE_CAUSES, ROLES, RULE, RULE_FINGERPRINT, evaluate, raw_lineage, verified_bindings,
)

INDEX = runtime.REGISTRY / "G3_INCIDENT_INDEX.json"
INDEX_SHA = INDEX.with_suffix(".sha256")
EQUIPMENT_ID = "lbnl-sd-ahu"


def window_evaluations(frame, first, end, registry):
    contexts = runtime.mode_contexts(frame, first, end)
    columns = [key for key in ROLES if key in frame]
    window = frame.iloc[first:end][columns]
    valid = verified_bindings(registry)
    for row, context in zip(window.itertuples(name=None), contexts):
        timestamp, *values = row
        yield timestamp, evaluate(dict(zip(columns, values)), context.fan_state, valid)


@lru_cache(maxsize=2)
def read_index(path, signature, expected_sha):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha or runtime.file_signature(path.stat()) != signature:
        runtime.fail(409, "INCIDENT_INDEX_INTEGRITY", "The frozen incident index differs from its registered SHA-256")
    try:
        index = json.loads(content)
    except (ValueError, UnicodeError):
        runtime.fail(409, "INCIDENT_INDEX_INTEGRITY", "The offline index is not valid JSON")
    if not isinstance(index, dict) or not isinstance(index.get("datasets"), dict):
        runtime.fail(409, "INCIDENT_INDEX_INTEGRITY", "The offline index has no dataset registry")
    if index.get("rule_fingerprint") != RULE_FINGERPRINT or index.get("index_version") != 1:
        runtime.fail(409, "INCIDENT_INDEX_STALE", "The incident index does not match the active rule policy")
    return index["datasets"]


def registered_record(dataset_id, source):
    try:
        path = runtime.DEMO_DIR / "incidents.json" if dataset_id == runtime.DEMO_ID else INDEX
        expected_sha = source["index_sha256"] if dataset_id == runtime.DEMO_ID else INDEX_SHA.read_text().strip()
        signature = runtime.file_signature(path.stat())
        indexed = read_index(path, signature, expected_sha).get(dataset_id)
    except FileNotFoundError:
        runtime.fail(409, "INCIDENT_INDEX_UNAVAILABLE", "The frozen incident index is unavailable")
    if indexed is None or indexed["source_sha256"] != source["sha256"]:
        runtime.fail(409, "INCIDENT_INDEX_STALE", "The incident index does not match this verified raw source")
    return indexed, expected_sha


def incident_snapshots(episodes, first, cutoff, source_sha, equipment_id=EQUIPMENT_ID):
    # Both ends are ordered because the single worker produces disjoint episodes.
    index = bisect_left(episodes, first, key=lambda event: event["closed_at"])
    for i in range(index, len(episodes)):
        event = episodes[i]
        if event["confirmed_at"] > cutoff:
            break
        last = min(event["last_seen"], cutoff)
        duration = (datetime.fromisoformat(last) - datetime.fromisoformat(event["first_observed"])).total_seconds()
        identity = f"{source_sha}:{equipment_id}:{RULE['method_id']}:{RULE_FINGERPRINT}:{event['first_observed']}"
        yield {
            "event_id": hashlib.sha256(identity.encode()).hexdigest(),
            "equipment_id": equipment_id,
            "method_id": RULE["method_id"],
            "kind": "RULE_SYMPTOM",
            "evidence_status": "CONFIRMED_SYMPTOM",
            "first_observed": event["first_observed"],
            "confirmed_at": event["confirmed_at"],
            "last_seen": last,
            "samples": int(duration / runtime.SAMPLE_SECONDS) + 1,
            "gap_reason": event["gap_reason"] if event["closed_at"] <= cutoff else "WINDOW_CUTOFF",
            "cause_status": "NO_ROOT_CAUSE_CONFIRMED",
            "possible_causes": list(POSSIBLE_CAUSES),
            "time_window": {"first": event["first_observed"], "last": event["confirmed_at"]},
            "raw_lineage": [root for stamp, values in event["confirmation_trace"]
                            for root in raw_lineage(values, source_sha, stamp)],
        }


def incidents(dataset_id, start, limit):
    if dataset_id == runtime.DEMO_ID:
        runtime.fail(404, "UNKNOWN_DATASET", "The legacy incident feed contains verified LBNL sources only")
    source, frame = runtime.mode_input_window(dataset_id, start, limit, require_index=True)
    return incident_window(dataset_id, source, frame, start, limit)


def incident_window(dataset_id, source, frame, start, limit, indexed=None):
    if not verified_bindings(runtime.SIGNALS):
        runtime.fail(409, "INCIDENT_INDEX_STALE", "The active BASIC signal bindings differ from the rule profile")
    if indexed is None:
        indexed, _ = registered_record(dataset_id, source)
    episodes = indexed["episodes"]
    first = runtime.start_index(frame.index, start)
    end = min(first + limit, len(frame))
    counts = {"samples": end - first, "evaluated": 0, "violated": 0, "not_evaluable": 0}
    reasons = {}
    for _, result in window_evaluations(frame, first, end, runtime.SIGNALS):
        if result.predicate == "NOT_EVALUABLE":
            counts["not_evaluable"] += 1
            reasons[result.reason_code] = reasons.get(result.reason_code, 0) + 1
        else:
            counts["evaluated"] += 1
            counts["violated"] += result.predicate == "VIOLATED"
    first_stamp = frame.index[first].isoformat() if end > first else None
    cutoff = frame.index[end - 1].isoformat() if end > first else None
    equipment = "demo-g4-ahu" if dataset_id == runtime.DEMO_ID else EQUIPMENT_ID
    return {
        "dataset_id": dataset_id,
        "clock_kind": runtime.CLOCK_KIND,
        "result_origin": runtime.result_origin(source),
        "source_sha256": source["sha256"],
        "rule": RULE,
        "rule_fingerprint": RULE_FINGERPRINT,
        "first": first_stamp,
        "last": cutoff,
        "coverage": counts,
        "not_evaluable_reasons": reasons,
        "inapplicable_checks": list(INAPPLICABLE_CHECKS),
        "next_start": frame.index[end].isoformat() if end < len(frame) else None,
        "events": list(incident_snapshots(episodes, first_stamp, cutoff, source["sha256"], equipment)) if cutoff else [],
    }
