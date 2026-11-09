"""A BASIC-only lower mixing-temperature envelope symptom for LBNL SD-AHU."""
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from backend.app.services.g2_mode import MODE_POLICY
from backend.app.services.g2_quality import SAMPLE_SECONDS, TEMPERATURE_SCREEN_DEGF, sample_number

ROLES = {
    "MA_TEMP": "MIXED_AIR_TEMPERATURE",
    "OA_TEMP": "OUTDOOR_AIR_TEMPERATURE",
    "RA_TEMP": "RETURN_AIR_TEMPERATURE",
    "SF_SPD_DM": "SIMULATED_FAN_STATUS",
    "SF_CS": "FAN_SPEED_COMMAND",
}
TEMPERATURES = ("MA_TEMP", "OA_TEMP", "RA_TEMP")
SOURCE_UNITS = {**dict.fromkeys(TEMPERATURES, "degF"), "SF_SPD_DM": "binary", "SF_CS": "fraction"}
SOURCE_KINDS = {**dict.fromkeys(TEMPERATURES, "MEASUREMENT"), "SF_SPD_DM": "STATUS", "SF_CS": "COMMAND"}
TOLERANCE_DEGF = 7.0
MIN_SEPARATION_DEGF = 10.0
MIN_COMMAND = 0.01
CONFIRM_SECONDS = 600
RULE = {
    "method_id": "mat-below-mixing-envelope",
    "model_or_rule_version": "1.0.0",
    "panel": "BASIC",
    "source_id": "Open-FDD/FC2@32a6d4479abed81f9d6d0ff426260cc8ad8e30e2",
    "reference_url": "https://github.com/bbartling/open-fdd/blob/32a6d4479abed81f9d6d0ff426260cc8ad8e30e2/open_fdd/rules/cookbook_catalog.py",
    "implementation": "LOCAL_FORMULA",
    "required_channel_roles": [{"canonical_id": key, "role": role, "unit": SOURCE_UNITS[key]}
                               for key, role in ROLES.items()],
    "mode_prerequisites": ["RUNNING", "SIMULATED_FAN_STATUS_ON", "FAN_SPEED_COMMAND_ABOVE_MINIMUM"],
    "sensor_quality_scope": "REQUIRED_INPUTS_ONLY",
    "threshold_basis": "PREDECLARED_ENGINEERING_TOLERANCE",
    "lower_margin_deg_f": TOLERANCE_DEGF,
    "min_inlet_separation_deg_f": MIN_SEPARATION_DEGF,
    "min_fan_command_exclusive": MIN_COMMAND,
    "confirmation_duration_seconds": CONFIRM_SECONDS,
    "flow_proof": "UNAVAILABLE_IN_BASIC",
}
RULE_FINGERPRINT = hashlib.sha256(json.dumps({
    "rule": RULE, "fan_policy": MODE_POLICY, "sample_seconds": SAMPLE_SECONDS,
    "temperature_screen_deg_f": TEMPERATURE_SCREEN_DEGF,
}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

MODE_BLOCKS = {"OFF": "FAN_OFF", "UNKNOWN": "FAN_STATUS_UNKNOWN", "TRANSITION_HOLD": "FAN_TRANSITION_HOLD"}
POSSIBLE_CAUSES = (
    "TEMPERATURE_SENSOR_ERROR_OR_PLACEMENT",
    "INCOMPLETE_MIXING_OR_TIME_MISMATCH",
    "UNOBSERVED_UPSTREAM_HEAT_EXCHANGE_OR_AIRFLOW",
)
INAPPLICABLE_CHECKS = (
    "FC3_RETURN_FAN_HEAT_UNVERIFIED", "SAT_TRACKING_COOLING_ENABLE_UNOBSERVED",
    "VALVE_TRACKING_FEEDBACK_UNAVAILABLE_IN_BASIC", "FLOW_BALANCE_UNAVAILABLE_IN_BASIC",
)


@dataclass(frozen=True)
class Evaluation:
    applicability: str
    predicate: str
    reason_code: str
    invalid_input_ids: tuple = ()
    values: dict | None = None


def verified_bindings(registry):
    """Anchor each role to its own documented LBNL point, with no alias fallback."""
    for key in ROLES:
        spec = registry.get(key, {})
        if (spec.get("source_column") != key or not spec.get("basic_eligible")
                or spec.get("source_unit") != SOURCE_UNITS[key] or spec.get("kind") != SOURCE_KINDS[key]):
            return False
    return True


def evaluate(row, mode, bindings_valid):
    if not bindings_valid:
        return Evaluation("INAPPLICABLE", "NOT_EVALUABLE", "UNVERIFIED_OR_DUPLICATE_BINDING")
    missing = tuple(key for key in ROLES if key not in row)
    if missing:
        return Evaluation("INAPPLICABLE", "NOT_EVALUABLE", "REQUIRED_INPUT_MISSING", missing)
    if mode != "RUNNING":
        reason = MODE_BLOCKS.get(mode, "FAN_STATUS_UNKNOWN")
        status = "INCONCLUSIVE" if reason == "FAN_STATUS_UNKNOWN" else "INAPPLICABLE"
        return Evaluation(status, "NOT_EVALUABLE", reason)
    values = {key: sample_number(row[key])[0] for key in ROLES}
    invalid = tuple(key for key, number in values.items() if number is None or (
        key in TEMPERATURES and not TEMPERATURE_SCREEN_DEGF[0] <= number <= TEMPERATURE_SCREEN_DEGF[1]
    ) or (key == "SF_SPD_DM" and number != 1) or (key == "SF_CS" and not 0 <= number <= 1))
    if invalid:
        return Evaluation("INCONCLUSIVE", "NOT_EVALUABLE", "REQUIRED_INPUT_QUALITY", invalid, values)
    if values["SF_CS"] <= MIN_COMMAND:
        return Evaluation("INCONCLUSIVE", "NOT_EVALUABLE", "FAN_COMMAND_TOO_LOW", values=values)
    outdoor, return_air = values["OA_TEMP"], values["RA_TEMP"]
    if abs(outdoor - return_air) < MIN_SEPARATION_DEGF:
        return Evaluation("INAPPLICABLE", "NOT_EVALUABLE", "LOW_INLET_TEMPERATURE_SEPARATION", values=values)
    violated = values["MA_TEMP"] < min(outdoor, return_air) - TOLERANCE_DEGF
    return Evaluation("APPLICABLE", "VIOLATED" if violated else "NOT_VIOLATED", "EVALUATED", values=values)


def raw_lineage(values, source_sha, timestamp):
    return [{
        "evidence_id": f"{source_sha}:{timestamp}:{key}",
        "source_sha256": source_sha,
        "source_column": key,
        "canonical_id": key,
        "timestamp": timestamp,
        "value": value,
        "unit": SOURCE_UNITS[key],
    } for key, value in (values or {}).items()]


def point_result(row, mode, registry, sha, timestamp):
    evaluation = evaluate(row, mode, verified_bindings(registry))
    return {
        "rule": RULE,
        "applicability": evaluation.applicability,
        "predicate": evaluation.predicate,
        "reason_code": evaluation.reason_code,
        "invalid_input_ids": list(evaluation.invalid_input_ids),
        "raw_lineage": raw_lineage(evaluation.values, sha, timestamp),
        "time_window": {"first": timestamp, "last": timestamp},
    }


class EpisodeAccumulator:
    """Consume consecutive observations. Confirmation uses only elapsed observed time."""

    def __init__(self):
        self.events = []
        self.previous = None
        self.first = None
        self.confirmed = None
        self.confirmation_trace = []

    def _close(self, stamp, reason):
        if self.confirmed is not None:
            self.events.append({
                "first_observed": self.first.isoformat(),
                "confirmed_at": self.confirmed.isoformat(),
                "last_seen": self.previous.isoformat(),
                "closed_at": stamp.isoformat(),
                "gap_reason": reason,
                "confirmation_trace": self.confirmation_trace,
            })
        self.first = self.confirmed = None
        self.confirmation_trace = []

    def feed(self, stamp, evaluation):
        if self.previous is not None:
            delta = stamp - self.previous
            step = timedelta(seconds=SAMPLE_SECONDS)
            if delta <= timedelta(0):
                raise ValueError("Expected increasing source-local observations")
            if delta != step:
                self._close(stamp, "TIME_GAP" if delta > step and delta % step == timedelta(0) else "OFF_GRID_STEP")
        if evaluation.predicate == "VIOLATED":
            if self.first is None:
                self.first = stamp
            if self.confirmed is None:
                self.confirmation_trace.append((stamp.isoformat(), evaluation.values))
                if (stamp - self.first).total_seconds() >= CONFIRM_SECONDS:
                    self.confirmed = stamp
        else:
            self._close(stamp, "PREDICATE_CLEARED" if evaluation.predicate == "NOT_VIOLATED" else evaluation.reason_code)
        self.previous = stamp

    def finish(self):
        if self.previous is not None:
            self._close(self.previous, "SOURCE_END")
        return self.events
