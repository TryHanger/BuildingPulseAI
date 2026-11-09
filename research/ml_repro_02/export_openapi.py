"""Export the additive research contract without changing the accepted Investigator contract."""
import json
from pathlib import Path

from backend.app.main import app


def schema():
    source = app.openapi()
    paths = {key: value for key, value in source["paths"].items() if key.startswith("/api/research/virtual-sensors")}
    assert len(paths) == 2
    components = {}

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].removeprefix("#/components/schemas/")
                if name not in components:
                    components[name] = source["components"]["schemas"][name]
                    walk(components[name])
            for value in node.values():
                walk(value)

    walk(paths)
    return {"openapi": source["openapi"], "info": {"title": "BuildingPulse Virtual Sensor Research", "version": "1.2.0"},
            "paths": paths, "components": {"schemas": components}}


if __name__ == "__main__":
    import sys
    Path(sys.argv[1]).write_text(json.dumps(schema(), indent=2, sort_keys=True) + "\n")
