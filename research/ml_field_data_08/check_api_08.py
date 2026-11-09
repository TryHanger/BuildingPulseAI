"""Assert that Stage 08 adds only three evidence limitations to Stage 07 responses."""
import argparse
import json
from pathlib import Path

from backend.app.main import app
from research.ml_domain_shift_07.export_contract_07 import main as export_research

LIMITS = {"self_attested_metadata_only", "one_dimensional_feature_ranges_only", "fan_duration_verified"}
SCHEMAS = {"ReducedSATResearchContract", "ApplicabilityResult"}


def main(stage07_schema, prior_stage06_schema, output):
    before = json.loads(stage07_schema.read_text())
    after = app.openapi()
    assert before["paths"] == after["paths"]
    original = before["components"]["schemas"]
    current = after["components"]["schemas"]
    assert original.keys() == current.keys()
    for name, schema in original.items():
        if name not in SCHEMAS:
            assert schema == current[name], name
            continue
        new = current[name]
        assert set(new["properties"]) - set(schema["properties"]) == LIMITS
        unchanged = {key: value for key, value in new["properties"].items() if key not in LIMITS}
        assert schema == {**new, "properties": unchanged}, name
    export_research(prior_stage06_schema, output)
    contract = json.loads(output.read_text())
    contract["info"]["version"] = "1.1.0"
    output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print("PASS Stage 07 route/schema parity; three additive response warnings only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stage07_schema", "prior_stage06_schema", "output"):
        parser.add_argument(name, type=Path)
    main(**vars(parser.parse_args()))
