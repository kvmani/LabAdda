"""Helpers for scheduled backups: status recording, bundle size and count-based retention.

Standard library only. Functions take plain paths so `lifecycle.py` keeps the locking,
journaling and service control, and these stay easy to test. Nothing here prints a path
into the status file or touches anything outside the directories it is given.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

import operations

# One shared status schema: the backend reads the file with the same module that writes it here.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from labadda import backup_status  # noqa: E402 — needs the backend directory on sys.path first

OPERATION_NAME = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{32}\Z")
ALIAS = backup_status.ALIAS_PATTERN


def status_directory(value: str | None) -> Path | None:
    """Return the validated status directory, or None when the site does not configure one."""
    if not value:
        return None
    directory = Path(value)
    if not directory.is_absolute():
        raise operations.OperationsError("LABADDA_STATUS_DIR must be an absolute path")
    info = directory.lstat() if directory.exists() or directory.is_symlink() else None
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise operations.OperationsError("LABADDA_STATUS_DIR must be an existing real directory")
    if info.st_mode & 0o022 or info.st_uid not in (0, os.geteuid()):
        raise operations.OperationsError(
            "Status directory must be operator-owned and not group/world writable"
        )
    return directory


def destination_alias(value: str) -> str:
    """Validate the short name shown for where backups are kept."""
    if not ALIAS.fullmatch(value):
        raise operations.OperationsError("Destination alias must be 1-32 lowercase letters, digits, - or _")
    return value


def bundle_size(bundle: Path) -> int:
    """Total bytes of the regular files in a finished bundle; links are never followed."""
    total = 0
    for directory, _, files in os.walk(bundle, followlinks=False):
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                total += path.stat().st_size
    return total


def record_outcome(
    directory: Path,
    *,
    destination: str,
    now: datetime | None = None,
    bundle: Path | None = None,
    schema: str | None = None,
    release: str | None = None,
    verification: str = "not_run",
) -> None:
    """Write the status for one run: a success when a verified bundle is given, else a failure."""
    succeeded = bundle is not None and verification == "passed"
    backup_status.write_status(
        directory,
        backup_status.BackupStatus(
            finished_at=(now or datetime.now(UTC)).replace(microsecond=0),
            result="success" if succeeded else "failure",
            size_bytes=bundle_size(bundle) if succeeded else None,
            verification=verification,
            destination=destination,
            schema=schema if succeeded else None,
            release=release if succeeded else None,
        ),
    )


def retention_plan(backup_root: Path, keep: int) -> dict:
    """List which finished backups a count-based retention would keep and remove.

    Only directories named like a lifecycle backup that hold a manifest count; anything else
    (a half-written bundle, a stray file) is reported and left alone.
    """
    if keep < 1:
        raise operations.OperationsError("Retention must keep at least one backup")
    finished = []
    ignored = 0
    for entry in backup_root.iterdir():
        manifest = entry / "manifest.json"
        is_backup = OPERATION_NAME.fullmatch(entry.name) and entry.is_dir() and not entry.is_symlink()
        if is_backup and manifest.is_file() and not manifest.is_symlink():
            finished.append(entry.name)
        else:
            ignored += 1
    finished.sort(reverse=True)
    return {
        "format": 1,
        "keep": keep,
        "kept": finished[:keep],
        "remove": finished[keep:],
        "ignored_entries": ignored,
        "applied": False,
    }


def apply_retention(backup_root: Path, plan: dict) -> dict:
    """Delete exactly the backups the plan lists, oldest first, then flush the directory."""
    for name in sorted(plan["remove"]):
        shutil.rmtree(backup_root / name)
    descriptor = os.open(backup_root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {**plan, "applied": True}
