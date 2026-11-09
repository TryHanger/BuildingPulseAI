from datetime import date, timedelta
from pathlib import Path
from shutil import copytree

import pytest

from research.field_apar_gate_14 import audit
from research.ml_field_observational_12 import replay as source

EVIDENCE = Path(__file__).parents[1] / "evidence/field_apar_gate_14"


def test_semantic_aliases_do_not_substitute_for_active_setpoint():
    protocol = audit.preregistration(EVIDENCE)
    headers = set(audit.EXCLUDED_SETPOINT_ALIASES) | {protocol["sat"], protocol["valve_command"], "fault"}
    fields = {key: (role, present) for key, role, present in audit.classify_columns(headers, protocol)}
    assert fields[protocol["sat_setpoint"]] == ("ACTIVE_SUPPLY_SETPOINT_CANDIDATE", False)
    assert fields[protocol["sat"]] == ("REPORTED_MEASUREMENT", True)
    assert fields[protocol["valve_command"]] == ("BAS_COMMAND", True)
    assert "fault" not in fields
    assert all(fields[key] == ("EXCLUDED_AS_SAT_SETPOINT", True) for key in audit.EXCLUDED_SETPOINT_ALIASES)


def test_new_header_cannot_bypass_calibration_or_mode():
    protocol = audit.preregistration(EVIDENCE)
    with pytest.raises(source.Stop, match="STOP_NEW_SETPOINT_HEADER_REQUIRES_SOURCE_REVIEW"):
        audit.classify_columns({protocol["sat_setpoint"]}, protocol)


def test_schedule_buffer_is_symmetric_and_stop_is_always_explicit():
    event = date(2019, 3, 8)
    for offset in (-2, -1, 0, 1, 2):
        text = audit.compare_reason(event + timedelta(days=offset), {event}, 1)
        assert ("SITE_INTERVENTION_DAY_OR_BUFFER" in text) == (abs(offset) <= 1)
        assert "NO_ACTIVE_SUPPLY_AIR_SETPOINT" in text and "THRESHOLDS_UNSET" in text


def test_altered_preregistration_is_rejected(tmp_path):
    folder = tmp_path / "evidence"
    copytree(EVIDENCE, folder)
    (folder / "PREREGISTRATION.json").write_text('{"threshold":0}')
    with pytest.raises(source.Stop, match="STOP_PREREGISTRATION_SHA_MISMATCH"):
        audit.preregistration(folder)


def test_missing_source_abstains(tmp_path):
    config = audit.preregistration(EVIDENCE)
    with pytest.raises(source.Stop, match="STOP_SOURCE_UNAVAILABLE"):
        source.verify_sources(tmp_path, EVIDENCE, config)
