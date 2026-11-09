import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_display_catalog_preserves_physical_scope_and_exclusions():
    with (ROOT / "research/g56/SENSOR_SEMANTICS_STATUS.csv").open(encoding="utf-8") as stream:
        audit = {row["signal_id"]: row for row in csv.DictReader(stream)}
    catalog = json.loads((ROOT / "frontend/src/fixtures/g56_sensor_evidence.json").read_text())
    for point in catalog["channels"]:
        assert point["source"] == audit[point["id"]]["source"]
        assert point["status"] == audit[point["id"]]["product_status"]
    assert audit["RBC_AHU2_BETWEEN_COIL"]["topology_status"] == "SCHEMATICALLY_PLAUSIBLE"
    assert audit["RBC_AHU2_BETWEEN_COIL"]["exclusion"] == "MAT_MINUS_BETWEEN_IS_COOLING_DROP:LOCATION_CONFLICT"
    assert audit["RBC_AHU2_SAT"]["independence"] == "UNVERIFIED"
    assert audit["RBC_CHW_FLOW"]["location_scope"] == "HYDRONIC_SCOPE_UNVERIFIED"
    assert audit["RBC_AHU2_BRANCH_FLOW"]["product_status"] == "NOT_AVAILABLE"
    assert all(point["status"] != "FIELD_IO_VERIFIED" for point in catalog["channels"])
    for point in ("MODELLED_COIL_DISCHARGE", "MODELLED_CHW_FLOW", "TRUE_VALVE_POSITION", "COIL_Q"):
        assert audit[point]["exclusion"] == "OUTSIDE_BASIC"
