"""Export only the additive research API and compare existing REST schemas."""
import argparse
import json
from pathlib import Path

from backend.app.main import app

PREFIX = "/api/research/domain-shift-07"


def main(before, output):
    original = json.loads(before.read_text())
    current = app.openapi()
    added = {key: value for key, value in current["paths"].items() if key.startswith(PREFIX)}
    if set(added) != {PREFIX, PREFIX + "/applicability"}:
        raise ValueError("Unexpected research route set")
    if original["paths"] != {key: value for key, value in current["paths"].items() if key not in added}:
        raise ValueError("Existing REST operation changed")
    for category, definitions in original["components"].items():
        if any(current["components"][category][key] != definition for key, definition in definitions.items()):
            raise ValueError("Existing REST schema changed")
    schemas = {}

    def collect(node):
        if isinstance(node, dict):
            if "$ref" in node:
                key = node["$ref"].removeprefix("#/components/schemas/")
                if key not in schemas:
                    schemas[key] = current["components"]["schemas"][key]
                    collect(schemas[key])
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(added)
    contract = {"openapi": current["openapi"], "info": {"title": "BuildingPulse Research Applicability", "version": "1.0.0"},
                "paths": added, "components": {"schemas": schemas}}
    output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
    print(f"PASS {len(original['paths'])} existing REST paths and all existing components unchanged; 2 additive research paths")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("output", type=Path)
    main(**vars(parser.parse_args()))
