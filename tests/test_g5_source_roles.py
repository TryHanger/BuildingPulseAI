from copy import deepcopy

import pytest

from research.g5.audit_sources import (
    COMMAND, FEATURES, nominal_support, source_identity, source_map, validate_features,
)


@pytest.mark.parametrize("extra", ["SYS_CTL", "CHWC_VLV", "source_label", "SA_TEMP", "ground_truth"])
def test_basic_rejects_privileged_columns(extra):
    with pytest.raises(ValueError, match="undeclared"):
        validate_features((*FEATURES, extra), "BASIC", source_map())


def test_roles_reject_aliased_command_and_false_extra_provenance():
    points = source_map()
    validate_features((*FEATURES, COMMAND), "BASIC", points)
    false_command = deepcopy(points)
    false_command[COMMAND]["kind"] = "MEASUREMENT"
    with pytest.raises(ValueError, match="Command"):
        validate_features((*FEATURES, COMMAND), "BASIC", false_command)
    points["CHWC_VLV"]["basic_eligible"] = True
    with pytest.raises(ValueError, match="provenance"):
        validate_features((*FEATURES, "CHWC_VLV"), "EXTRA_SIMULATED", points)
    with pytest.raises(ValueError, match="panel"):
        validate_features(FEATURES, "FIELD", points)


def test_duplicate_labels_and_matching_times_do_not_form_trials():
    shared = {"sha256": "same-bytes", "first": "2018-01-01", "last": "2018-12-31"}
    first = source_identity({**shared, "path": "oa_bias_2_annual.csv"}, "release")
    second = source_identity({**shared, "path": "oa_bias_4_annual.csv"}, "release")
    assert first["source_id"] == second["source_id"]
    assert first["label_status"] == second["label_status"] == "EXCLUDED_DUPLICATE_SEVERITY"
    valve = source_identity({**shared, "path": "coi_stuck_025_annual.csv"}, "release")
    assert valve["pair_status"] == "PAIR_NOT_VERIFIED"
    assert valve["verified_onset"] is None
    assert valve["field_feedback"] is False


def test_constant_binary_status_has_no_transition_support_and_unknown_resets_hold(tmp_path):
    path = tmp_path / "source.csv"
    columns = "Datetime,SF_SPD_DM,MA_TEMP,OA_TEMP,RA_TEMP,SA_TEMP,SA_TEMPSPT,SF_CS,CHWC_VLV_DM\n"

    def inspect(values):
        path.write_text(columns + "".join(
            f"2018-01-01 01:{i:02d}:00,{value},60,40,70,55,55,0.5,0.5\n"
            for i, value in enumerate(values)
        ))
        return nominal_support(path)["train"]

    constant = inspect([1] * 7)
    assert constant["finite_common_panel"] == 2 and not constant["has_both_binary_states"]
    unknown = inspect([1] * 5 + [0.5] + [1] * 5)
    assert unknown.get("finite_common_panel", 0) == 0
    assert unknown["fan_status_counts"]["0.5"] == 1
