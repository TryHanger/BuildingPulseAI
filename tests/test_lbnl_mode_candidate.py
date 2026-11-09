from datetime import datetime, timedelta

from research.g0_g1_mode_candidate import evaluate_modes


def evaluate(*observations):
    start = datetime(2018, 1, 1, 22)
    return evaluate_modes([
        (start + timedelta(minutes=minute), {"SF_SPD_DM": fan, "OA_TEMP": oat})
        for minute, fan, oat in observations
    ])


def test_economizer_band_is_context_and_cooling_enable_is_unobserved():
    result = evaluate(*[(minute, 1, 45) for minute in range(6)])[-1]
    assert result.fan_state == "RUNNING"
    assert result.economizer_band == "WITHIN_DOCUMENTED_OAT_BAND"
    assert result.mechanical_cooling_enable == "UNOBSERVED"
    assert evaluate(*[(minute, 1, 80) for minute in range(6)])[-1].economizer_band == "OUTSIDE_DOCUMENTED_OAT_BAND"


def test_night_cycling_gap_and_invalid_status_restart_the_hold():
    result = evaluate((0, 0, 45), (1, 1, 45), (2, 0, 45), (3, 1, 45),
                      (4, 0.5, 45), (5, 1, 45), (545, 1, 45))
    assert [point.fan_state for point in result] == [
        "OFF", "TRANSITION_HOLD", "OFF", "TRANSITION_HOLD",
        "UNKNOWN", "TRANSITION_HOLD", "TRANSITION_HOLD",
    ]
    assert all(point.economizer_band == "UNASSESSED" for point in result)


def test_extra_oracle_cannot_change_basic_mode():
    start = datetime(2018, 1, 1)
    rows = [(start + timedelta(minutes=i), {"SF_SPD_DM": 1, "OA_TEMP": 45}) for i in range(6)]
    extras = [(stamp, {**row, "SYS_CTL": 1, "CHWC_VLV": 1, "SA_SP": 400}) for stamp, row in rows]
    assert evaluate_modes(rows) == evaluate_modes(extras)


def test_first_running_sample_and_temperature_boundaries_are_conservative():
    assert evaluate((0, 1, 45))[0].fan_state == "TRANSITION_HOLD"
    for oat, expected in ((33.8, "BOUNDARY_UNVERIFIED"), (60, "BOUNDARY_UNVERIFIED"),
                          (float("nan"), "UNASSESSED"), (None, "UNASSESSED")):
        assert evaluate(*[(minute, 1, oat) for minute in range(6)])[-1].economizer_band == expected
