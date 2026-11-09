"""Opt-in protection for isolated test and demonstration processes."""
import os
import sys
from pathlib import Path

from sqlalchemy.engine import make_url


def protect_audit_storage(settings):
    scratch = os.environ.get("BUILDINGPULSE_AUDIT_SCRATCH")
    if not scratch:
        return
    scratch = Path(scratch).resolve(strict=True)
    sources = [Path(path).resolve(strict=True) for path in
               os.environ["BUILDINGPULSE_PROTECTED_ROOTS"].split(os.pathsep)]
    if scratch == Path("/") or any(
        scratch.is_relative_to(source) or source.is_relative_to(scratch) for source in sources
    ):
        raise RuntimeError("Audit scratch overlaps a protected source")

    def in_scratch(path):
        return Path(os.fsdecode(path)).resolve().is_relative_to(scratch)

    url = make_url(settings.DATABASE_URL)
    if (url.get_backend_name() != "sqlite" or not url.database or url.query
            or not Path(url.database).is_absolute() or not in_scratch(url.database)
            or not in_scratch(settings.data_dir)):
        raise RuntimeError("Audit requires SQLite and DATA_ROOT inside scratch")

    def guard(event, args):
        if event == "sqlite3.connect" and not in_scratch(args[0]):
            raise RuntimeError("SQLite connection outside audit scratch")
        if event == "open":
            path, _, flags = args
            if isinstance(path, int) or not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                return
            paths = [path]
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime"}:
            paths = [args[0]]
        elif event in {"os.rename", "os.link", "os.symlink"}:
            paths = args[:2]
        else:
            return
        for path in paths:
            if isinstance(path, (str, bytes, Path)):
                resolved = Path(os.fsdecode(path)).resolve()
                if any(resolved.is_relative_to(source) for source in sources):
                    raise RuntimeError(f"Write to protected audit source: {resolved}")

    sys.addaudithook(guard)
