#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
scratch=$(realpath -m "${1:?Pass a new scratch directory outside the extracted package}")
case "$scratch/" in
  "$source_dir/"*) echo "Scratch must be outside the source tree" >&2; exit 1 ;;
esac
mkdir "$scratch"
(
  cd "$source_dir"
  tar --exclude=node_modules --exclude=dist --exclude=__pycache__ --exclude=.pytest_cache \
    -cf - backend contracts data frontend ml models research scripts tests buildingpulse.db \
    README.md requirements.txt .dockerignore .env.example docker-compose.yml
) | tar -xf - -C "$scratch"
mkdir "$scratch/tmp"
printf 'export BUILDINGPULSE_AUDIT_SCRATCH=%q\n' "$scratch"
printf 'export BUILDINGPULSE_PROTECTED_ROOTS=%q\n' "$source_dir"
printf 'export DATABASE_URL=%q\n' "sqlite:///$scratch/buildingpulse.db"
printf 'export DATA_ROOT=%q\n' "$scratch/data"
printf 'export TMPDIR=%q\n' "$scratch/tmp"
printf 'export MPLCONFIGDIR=%q\n' "$scratch/tmp/mpl"
printf 'export PYTHONDONTWRITEBYTECODE=1\n'
printf 'cd %q\n' "$scratch"
