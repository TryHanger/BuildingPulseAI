"""Executable G1 contract checks. Import into review tests, not the legacy API."""
import json
from datetime import datetime
from math import isfinite
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_DIR = Path(__file__).resolve().parent
OPENAPI = json.loads((CONTRACT_DIR / "openapi-v1.yaml").read_text(encoding="utf-8"))


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def validate_schema(document, component):
    schema = {
        "$ref": f"#/components/schemas/{component}",
        "components": OPENAPI["components"],
    }
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document), None)
    if error:
        location = "/".join(str(part) for part in error.absolute_path)
        raise ContractError(f"SCHEMA {location}: {error.message}")


def utc(value):
    return datetime.fromisoformat(value)


def window_times(window, digest):
    start, end, cutoff = (utc(window[key]) for key in ("from_utc", "to_utc", "cutoff_utc"))
    require(start < end <= cutoff and window["source_sha256"] == digest, "WINDOW_PROVENANCE")
    return start, end, cutoff


def validate_observation(observation, evidence, registry, bounds):
    spec = registry["methods"].get(observation["method_id"])
    require(spec is not None and spec["version"] == observation["method_version"]
            and spec["comparison_id"] == observation["comparison_id"], "UNKNOWN_METHOD")
    start, end, cutoff = window_times(observation["window"], evidence["source_sha256"])
    require(bounds[0] <= start and end <= bounds[1] and cutoff <= bounds[2], "WINDOW_OUTSIDE_SCOPE")
    provenance = observation["provenance_type"]
    if provenance != "POLICY":
        expected = "SYNTHETIC_FIXTURE" if evidence["source_type"] == "DEMO_FIXTURE" else "RECORDED"
        require(provenance == expected, "SOURCE_TYPE_MISMATCH")

    regime = observation["applicability"]["regime"]
    require(regime == spec.get("regime", "UNKNOWN"), "UNVERIFIED_REGIME")
    require(regime != "OFF" or observation["predicate"] == "INDETERMINATE", "OFF_PREDICATE")
    roles = spec["roles"]
    present = set()
    physical_ids = set()
    for root in observation["roots"]:
        signal = root["canonical_id"]
        registration = registry["signals"].get(signal)
        require(registration is not None, "UNKNOWN_CANONICAL_SIGNAL")
        require(all(root[key] == evidence[key] for key in ("dataset_id", "equipment_id", "source_sha256"))
                and root["physical_sensor_id"] == registration["physical_sensor_id"]
                and root["source_column"] in registration["columns"], "ROOT_SOURCE_IDENTITY")
        require(evidence["panel"] != "BASIC" or registration["basic"], "BASIC_CHANNEL_FORBIDDEN")
        require(registration.get("analytic", True), "ANALYTIC_CHANNEL_FORBIDDEN")
        require(root["role"] == roles.get(signal), "SIGNAL_ROLE_MISMATCH")
        require(signal not in present, "DUPLICATE_CANONICAL_ROOT")
        present.add(signal)
        physical_id = root["physical_sensor_id"]
        if physical_id is not None:
            require(physical_id not in physical_ids, "DUPLICATE_PHYSICAL_ROOT")
            physical_ids.add(physical_id)

    applicability = observation["applicability"]
    missing = set(roles) - present
    require(set(applicability["missing_roles"]) == {roles[signal] for signal in missing},
            "MISSING_ROLE_MISMATCH")
    if applicability["method_status"] == "APPLICABLE":
        require(not missing and observation["data_status"] == "VALID", "APPLICABILITY_MISMATCH")
    if observation["data_status"] == "INVALID":
        require(applicability["method_status"] == "INCONCLUSIVE", "INVALID_DATA_METHOD_STATUS")

    for value in observation["values"] + ([observation["threshold"]] if observation["threshold"] else []):
        require(isfinite(value["value"]), "NON_FINITE_VALUE")
        require(value["value_class"] != "VERIFIED_TRUTH", "TRUTH_IN_ANALYTIC_EVIDENCE")
    if observation["threshold"]:
        require(observation["threshold"]["value_class"] == "DERIVED_SCORE", "THRESHOLD_VALUE_CLASS")


def validate_event(evidence, observations, bounds, registry):
    event = evidence["event"]
    if event is None:
        return
    require(event["dataset_id"] == evidence["dataset_id"]
            and event["source_sha256"] == evidence["source_sha256"], "EVENT_SOURCE_IDENTITY")
    # Event identifiers and algorithm version are supplied by the analysis store.
    registered = registry.get("events", {}).get(event["event_id"])
    require(registered is not None and registered == event, "EVENT_REGISTRY_MISMATCH")
    start, confirmation = utc(event["started_at"]), utc(event["confirmed_at"])
    end = utc(event["ended_at"]) if event["ended_at"] else bounds[1]
    require(bounds[0] <= start <= confirmation < end <= bounds[1], "EVENT_TIME_ORDER")
    triggers = event["trigger_observation_ids"]
    require(len(set(triggers)) == len(triggers), "EVENT_DUPLICATE_TRIGGER")
    for trigger in triggers:
        observation = observations.get(trigger)
        require(observation is not None and observation["predicate"] == "VIOLATED", "EVENT_TRIGGER")
        window = observation["window"]
        require(max(start, utc(window["from_utc"])) < min(end, utc(window["to_utc"])), "EVENT_TRIGGER_TIME")


def display_for(observations):
    positive = [item for item in observations if item["predicate"] == "VIOLATED"]
    negative = [item for item in observations if item["predicate"] == "NOT_VIOLATED"]
    for left in positive:
        for right in negative:
            if left["comparison_id"] != right["comparison_id"]:
                continue
            if left["applicability"]["regime"] != right["applicability"]["regime"]:
                continue
            a, b = left["window"], right["window"]
            if max(utc(a["from_utc"]), utc(b["from_utc"])) < min(utc(a["to_utc"]), utc(b["to_utc"])):
                return "CONFLICTED", "CONFLICT"
    if positive:
        return "DETECTED", "ALARM"
    if negative:
        return "NOT_DETECTED_IN_EVALUATED_TESTS", "NO_ALARM"
    return "UNASSESSED", "NOT_EVALUABLE"


def validate_evidence(evidence, registry, *, confirmed_incident=False):
    """The caller supplies a trusted registry, never material from the payload."""
    validate_schema(evidence, "EvidenceV1")
    require(all(evidence[key] == registry[key] for key in (
        "dataset_id", "equipment_id", "source_type", "source_sha256")), "DATASET_REGISTRY_MISMATCH")
    require(evidence["model_scope"] == "UNKNOWN", "UNVERIFIED_MODEL_SCOPE")
    bounds = window_times(evidence["window"], evidence["source_sha256"])
    observations = {}
    quality = set()
    for item in evidence["observations"]:
        require(item["observation_id"] not in observations, "DUPLICATE_OBSERVATION")
        validate_observation(item, evidence, registry, bounds)
        observations[item["observation_id"]] = item
        quality.add(item["data_status"])
    aggregate = next(iter(quality)) if len(quality) == 1 else ("DEGRADED" if quality else "UNKNOWN")
    require(evidence["data_status"] == aggregate, "DATA_STATUS_MISMATCH")
    require((evidence["anomaly_status"], evidence["display_state"]) == display_for(observations.values()),
            "ANOMALY_STATUS_MISMATCH")
    require(evidence["cause_status"] in ("NOT_ASSESSED", "UNEXPLAINED", "AMBIGUOUS"), "NO_VALIDATED_CAUSAL_REGISTRY")
    if evidence["cause_status"] == "AMBIGUOUS":
        require(len({item["hypothesis_id"] for item in evidence["hypotheses"]}) >= 2, "EMPTY_CAUSAL_AMBIGUITY")
    for item in evidence["hypotheses"]:
        require(item["hypothesis_id"] in registry.get("hypothesis_ids", ()), "UNKNOWN_HYPOTHESIS")
        require(item["status"] == "UNKNOWN" and item["discriminating_test_id"] is None
                and not item["observation_ids"], "UNSUPPORTED_CAUSAL_CLAIM")
    if confirmed_incident:
        require(evidence["event"] is not None, "CONFIRMED_INCIDENT_REQUIRES_EVENT")
    validate_event(evidence, observations, bounds, registry)
