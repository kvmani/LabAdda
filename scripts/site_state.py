"""Durable on-disk primitives for site operations: fsynced directories, the lock and the journal.

Standard library only.
"""

from __future__ import annotations

import fcntl
import json
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

import operations


def sync_directory(path: Path):
    fd = os.open(path, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_directory(path: Path):
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise operations.OperationsError(
            "Operator state/backup directory must be private and owned by this operator"
        )


@contextmanager
def locked(root: Path):
    state = root / "operations"
    private_directory(state)
    fd = os.open(state / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise operations.OperationsError("Another site operation is running") from None
        yield state
    finally:
        os.close(fd)


def journal(path: Path, event: str, **fields):
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps({"at": time.time(), "event": event, **fields}, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())
    sync_directory(path.parent)
