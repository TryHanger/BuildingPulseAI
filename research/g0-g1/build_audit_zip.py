"""Package actual review inputs and compute a checksum for every included file."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DIRECTORIES = (
    "backend", "contracts", "data", "frontend/src", "ml", "models", "scripts", "tests",
    "research/g0-g1", "research/protocols", "research/reports", "research/runs",
    "research/splits", "research/tables",
)
FILES = (
    "AGENTS.md", "BUILDINGPULSE_MASTER_IMPLEMENTATION_PLAN.md", "DECISION_REGISTER_SEED.md",
    "HANDOFF_AND_ACCEPTANCE.md", "README.md", ".dockerignore", ".env.example",
    "requirements.txt", "docker-compose.yml", "buildingpulse.db", "run_csiro_validation.py",
    "docs/STATE.md", "docs/DECISIONS.md", "docs/NEXT_STEPS.md", "docs/DATA_DICTIONARY.md",
    "docs/LBNL_FDD_Data_Sets_SDAHU.pdf", "frontend/Dockerfile", "frontend/package.json",
    "frontend/package-lock.json", "frontend/vite.config.ts", "frontend/tsconfig.json",
    "frontend/index.html", "frontend/postcss.config.js", "frontend/tailwind.config.js",
)

def included(path):
    return (
        path.is_file() and not path.is_symlink()
        and not ({"__pycache__", ".pytest_cache", ".git", "node_modules"} & set(path.parts))
        and path.name not in {".env", ".coverage"}
        and path.suffix not in {".pyc", ".tmp"}
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    files = {root / filename for filename in FILES}
    for dirname in DIRECTORIES:
        files.update(path for path in (root / dirname).rglob("*") if included(path))
    sums = []
    with ZipFile(args.output, "w", compression=ZIP_DEFLATED, compresslevel=4) as archive:
        for path in sorted(files):
            name = path.relative_to(root).as_posix()
            digest = hashlib.sha256()
            with path.open("rb") as source, archive.open(name, "w") as target:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
                    target.write(block)
            sums.append(f"{digest.hexdigest()}  {name}\n")
        archive.writestr("SHA256SUMS.txt", "".join(sums))
    with args.output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    args.output.with_suffix(".zip.sha256").write_text(f"{digest}  {args.output.name}\n", encoding="ascii")
    print(f"{len(sums)} verified-input entries recorded in {args.output} ({args.output.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
