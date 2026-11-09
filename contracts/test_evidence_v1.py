import hashlib
import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from contracts.evidence_v1 import CONTRACT_DIR, OPENAPI, ContractError, validate_evidence, validate_schema


def read(name):
    return json.loads((CONTRACT_DIR / "fixtures" / name).read_text(encoding="utf-8"))


def registry_for(name):
    registry = read("demo_registry.json")
    digest = hashlib.sha256((CONTRACT_DIR / "fixtures" / "demo_registry.json").read_bytes()).hexdigest()
    registry["source_sha256"] = digest
    if name in {"alarm", "conflict", "invalid-sat-independent-alarm"}:
        trigger = "oat-1" if name == "invalid-sat-independent-alarm" else "sat-1"
        registry["events"] = {
            "demo-event": {
                "event_id": "demo-event", "run_id": "demo-run", "dataset_id": "demo-ahu",
                "source_sha256": digest, "trigger_observation_ids": [trigger],
                "aggregation_version": "fixture-1", "started_at": "2026-01-01T08:00:00Z",
                "confirmed_at": "2026-01-01T08:02:00Z", "ended_at": "2026-01-01T08:05:00Z",
            }
        }
    return registry


def test_openapi_and_components():
    validate(OPENAPI)
    for schema in OPENAPI["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("filename,metadata", read("demo_manifest.json").items())
def test_handoff_fixture(filename, metadata):
    document = read(filename)
    assert metadata["demo_fixture"] is True
    assert metadata["contract_revision"] == OPENAPI["info"]["version"]
    assert metadata["source_type"] == document["source_type"]
    if metadata["schema"] == "EvidenceV1":
        validate_evidence(document, registry_for(filename.removesuffix(".json")))
    else:
        validate_schema(document, "Dataset")


@pytest.mark.parametrize(("name", "path", "replacement", "error"), [
    ("alarm", ("anomaly_status",), "detected", "SCHEMA"),
    ("alarm", ("model_scope",), 1, "SCHEMA"),
    ("alarm", ("observations", 0, "roots", 0, "role"), "INPUT", "SCHEMA"),
    ("alarm", ("observations", 0, "applicability", "method_status"), "INAPPLICABLE", "SCHEMA"),
    ("alarm", ("data_status",), "INVALID", "DATA_STATUS_MISMATCH"),
    ("alarm", ("observations", 0, "data_status"), "INVALID", "SCHEMA"),
    ("invalid-sat", ("observations", 0, "applicability", "method_status"), "INAPPLICABLE", "INVALID_DATA_METHOD_STATUS"),
    ("conflict", ("anomaly_status",), "DETECTED", "ANOMALY_STATUS_MISMATCH"),
    ("alarm", ("validated_discriminator",), True, "SCHEMA"),
    ("missing-feedback", ("display_state",), "NO_ALARM", "ANOMALY_STATUS_MISMATCH"),
    ("alarm", ("observations", 0, "roots", 0, "physical_sensor_id"), "another-sat", "ROOT_SOURCE_IDENTITY"),
    ("alarm", ("observations", 0, "roots", 0, "dataset_id"), "another-release", "ROOT_SOURCE_IDENTITY"),
    ("alarm", ("observations", 0, "roots", 0, "canonical_id"), "SAT", "UNKNOWN_CANONICAL_SIGNAL"),
    ("alarm", ("observations", 0, "roots", 0, "source_column"), "OTHER_SAT", "ROOT_SOURCE_IDENTITY"),
    ("alarm", ("observations", 0, "roots"), [], "SCHEMA"),
    ("alarm", ("observations", 0, "roots", 0, "role"), "CONTEXT", "SIGNAL_ROLE_MISMATCH"),
    ("alarm", ("event", "run_id"), "fabricated-run", "EVENT_REGISTRY_MISMATCH"),
    ("alarm", ("event", "source_sha256"), "0" * 64, "EVENT_SOURCE_IDENTITY"),
    ("alarm", ("probability",), 0.73, "SCHEMA"),
    ("alarm", ("observations", 0, "values", 0, "probability"), 0.73, "SCHEMA"),
    ("alarm", ("observations", 0, "values", 0, "value_class"), "VERIFIED_TRUTH", "TRUTH_IN_ANALYTIC_EVIDENCE"),
    ("alarm", ("observations", 0, "values", 0, "value"), float("nan"), "NON_FINITE_VALUE"),
    ("alarm", ("cause_status",), "ISOLATED_CONDITIONAL", "NO_VALIDATED_CAUSAL_REGISTRY"),
    ("alarm", ("cause_status",), "CONFIRMED_EXTERNALLY", "NO_VALIDATED_CAUSAL_REGISTRY"),
])
def test_reviewer_cases(name, path, replacement, error):
    document = read(name + ".json")
    node = document
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = replacement
    with pytest.raises(ContractError, match=error):
        validate_evidence(document, registry_for(name))


def test_alias_resolves_only_in_source_and_cannot_double_count():
    document = read("alarm.json")
    roots = document["observations"][0]["roots"]
    roots[0]["source_column"] = "SAT"
    validate_evidence(document, registry_for("alarm"))
    duplicate = deepcopy(roots[0])
    duplicate["source_column"] = "SA_TEMP"
    roots.append(duplicate)
    with pytest.raises(ContractError, match="DUPLICATE_CANONICAL_ROOT"):
        validate_evidence(document, registry_for("alarm"))


@pytest.mark.parametrize("channel", ["CHWC_VLV", "SYS_CTL"])
def test_extra_roots_in_basic_fail(channel):
    document = read("missing-feedback.json")
    registry = registry_for("missing-feedback")
    observation = document["observations"][0]
    registry["methods"][observation["method_id"]]["roles"] = {channel: "TARGET"}
    observation["applicability"]["missing_roles"] = []
    observation["roots"] = [{
        **{key: document[key] for key in ("dataset_id", "equipment_id", "source_sha256")},
        "canonical_id": channel, "source_column": channel, "role": "TARGET",
        "physical_sensor_id": registry["signals"][channel]["physical_sensor_id"],
    }]
    with pytest.raises(ContractError, match="BASIC_CHANNEL_FORBIDDEN"):
        validate_evidence(document, registry)


def test_known_hypothesis_cannot_assert_support():
    document = read("alarm.json")
    registry = registry_for("alarm")
    registry["hypothesis_ids"] = {"valve-stuck"}
    document["hypotheses"] = [{"hypothesis_id": "valve-stuck", "status": "SUPPORTED",
                               "observation_ids": ["sat-1"], "discriminating_test_id": None}]
    with pytest.raises(ContractError, match="UNSUPPORTED_CAUSAL_CLAIM"):
        validate_evidence(document, registry)


def test_registered_event_still_requires_violating_trigger():
    document = read("alarm.json")
    registry = registry_for("alarm")
    document["event"]["trigger_observation_ids"] = ["invented"]
    registry["events"]["demo-event"] = deepcopy(document["event"])
    with pytest.raises(ContractError, match="EVENT_TRIGGER"):
        validate_evidence(document, registry)


def test_client_configuration_rejects_manual_discriminator():
    document = {"dataset_id": "demo-ahu", "equipment_id": "demo-ahu-01", "panel": "BASIC",
                "start": "2026-01-01T08:00:00Z", "end": "2026-01-01T08:05:00Z",
                "cutoff_utc": "2026-01-01T08:05:00Z", "method_ids": ["demo-sat-deviation"]}
    validate_schema(document, "AnalysisRequest")
    document["validated_discriminator"] = "test-123"
    with pytest.raises(ContractError, match="SCHEMA"):
        validate_schema(document, "AnalysisRequest")


def test_sys_ctl_is_unavailable_to_analytics_in_extra():
    document = read("missing-feedback.json")
    registry = registry_for("missing-feedback")
    document["panel"] = "EXTRA"
    observation = document["observations"][0]
    registry["methods"][observation["method_id"]]["roles"] = {"SYS_CTL": "TARGET"}
    observation["applicability"]["missing_roles"] = []
    observation["roots"] = [{
        **{key: document[key] for key in ("dataset_id", "equipment_id", "source_sha256")},
        "canonical_id": "SYS_CTL", "source_column": "SYS_CTL", "role": "TARGET",
        "physical_sensor_id": None,
    }]
    with pytest.raises(ContractError, match="ANALYTIC_CHANNEL_FORBIDDEN"):
        validate_evidence(document, registry)


def test_distinct_canonical_names_cannot_duplicate_same_physical_root():
    document = read("alarm.json")
    registry = registry_for("alarm")
    observation = document["observations"][0]
    registry["signals"]["OA_TEMP"]["physical_sensor_id"] = "demo-sat"
    observation["roots"][2]["physical_sensor_id"] = "demo-sat"
    with pytest.raises(ContractError, match="DUPLICATE_PHYSICAL_ROOT"):
        validate_evidence(document, registry)


def test_off_cannot_report_violated_even_if_regime_is_registered():
    document = read("alarm.json")
    observation = document["observations"][0]
    observation["applicability"]["regime"] = "OFF"
    registry = registry_for("alarm")
    registry["methods"][observation["method_id"]]["regime"] = "OFF"
    with pytest.raises(ContractError, match="OFF_PREDICATE"):
        validate_evidence(document, registry)


def test_scope_cannot_be_promoted_without_registered_model():
    document = read("alarm.json")
    document["model_scope"] = "IN_SCOPE"
    with pytest.raises(ContractError, match="UNVERIFIED_MODEL_SCOPE"):
        validate_evidence(document, registry_for("alarm"))


def test_payload_cannot_select_regime():
    document = read("alarm.json")
    document["observations"][0]["applicability"]["regime"] = "ECONOMIZER"
    with pytest.raises(ContractError, match="UNVERIFIED_REGIME"):
        validate_evidence(document, registry_for("alarm"))


def test_ambiguity_requires_registered_alternatives():
    document = read("alarm.json")
    document["cause_status"] = "AMBIGUOUS"
    with pytest.raises(ContractError, match="EMPTY_CAUSAL_AMBIGUITY"):
        validate_evidence(document, registry_for("alarm"))


def test_detection_does_not_mint_a_confirmed_incident():
    document = read("alarm.json")
    document["event"] = None
    registry = registry_for("alarm")
    validate_evidence(document, registry)
    with pytest.raises(ContractError, match="CONFIRMED_INCIDENT_REQUIRES_EVENT"):
        validate_evidence(document, registry, confirmed_incident=True)


@pytest.mark.parametrize("name", ["no-alarm", "missing-feedback", "invalid-sat"])
def test_unassessed_or_negative_anomaly_cannot_claim_unexplained_cause(name):
    document = read(name + ".json")
    document["cause_status"] = "UNEXPLAINED"
    with pytest.raises(ContractError, match="SCHEMA"):
        validate_evidence(document, registry_for(name))
