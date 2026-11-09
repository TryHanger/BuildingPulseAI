"""Typecheck fixture literals against the OpenAPI-generated TypeScript types."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

DIRECTORY = Path(__file__).resolve().parent

def main():
    npx = sys.argv[1] if len(sys.argv) > 1 else "npx"
    manifest = json.loads((DIRECTORY / "fixtures/demo_manifest.json").read_text())
    with TemporaryDirectory() as temporary:
        work = Path(temporary)
        subprocess.run([npx, "--yes", "openapi-typescript@7.10.1",
                        str(DIRECTORY / "openapi-v1.yaml"), "-o", str(work / "api.d.ts")], check=True)
        lines = ["import type { components } from './api';"]
        for index, (filename, metadata) in enumerate(manifest.items()):
            payload = (DIRECTORY / "fixtures" / filename).read_text(encoding="utf-8").strip()
            lines.append(f"export const fixture{index} = {payload} satisfies components['schemas']['{metadata['schema']}'];")
        (work / "fixtures.ts").write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run([npx, "--yes", "--package", "typescript@5.7.3", "tsc",
                        "--strict", "--noEmit", str(work / "fixtures.ts")], check=True)
        print(f"TypeScript checked {len(manifest)} fixtures.")

if __name__ == "__main__":
    main()
