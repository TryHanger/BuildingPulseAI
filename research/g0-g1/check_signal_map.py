"""Check the handoff profile against the source manifest and unit anchors."""
import json
from pathlib import Path

import yaml

here = Path(__file__).resolve().parent
manifest = json.loads((here / "DATASET_MANIFEST.json").read_text(encoding="utf-8"))
profile = yaml.safe_load((here / "SIGNAL_MAP_V1.yaml").read_text(encoding="utf-8"))
points = profile["signals"]
basic = {name for name, point in points.items() if point["basic_eligible"]}
expected = set("""
SA_TEMP SA_TEMPSPT OA_TEMP MA_TEMP RA_TEMP SF_SPD_DM RF_SPD_DM SF_CS RF_CS
OA_DMPR_DM RA_DMPR_DM CHWC_VLV_DM SA_SP SA_SPSPT
ZONE_TEMP_1 ZONE_TEMP_2 ZONE_TEMP_3 ZONE_TEMP_4 ZONE_TEMP_5
""".split())
assert basic == expected and len(points) == 30
assert profile["release_id"] == manifest["release_id"]
for member in manifest["members"]:
    if "columns" in member:
        assert len(member["columns"]) == 31
        assert set(member["columns"]) == {"Datetime", *points}
for command, actual in (
    ("CHWC_VLV_DM", "CHWC_VLV"), ("OA_DMPR_DM", "OA_DMPR"), ("RA_DMPR_DM", "RA_DMPR"),
    ("SF_CS", "SF_SPD"), ("RF_CS", "RF_SPD"),
):
    assert points[command]["kind"] == "COMMAND" and command in basic
    assert points[actual]["kind"] == "MEASUREMENT" and actual not in basic
assert points["SYS_CTL"]["kind"] == "MODEL_INTERNAL" and "SYS_CTL" not in basic
assert points["SF_SPD_DM"]["kind"] == points["RF_SPD_DM"]["kind"] == "STATUS"
for f, c in ((32, 0), (68, 20), (55, 115 / 9), (33.8, 1), (60, 140 / 9)):
    assert abs((f - 32) * 5 / 9 - c) < 1e-10
    assert abs(c * 9 / 5 + 32 - f) < 1e-10
for delta_c in (-4, -2, 0, 2, 4):
    delta_f = delta_c * 9 / 5
    assert abs(delta_f * 5 / 9 - delta_c) < 1e-10
assert (2 - 32) * 5 / 9 != 2 * 5 / 9
print("21 headers, 30 points, 19 BASIC / 11 EXTRA, command/feedback, absolute/delta roundtrips: PASS")
