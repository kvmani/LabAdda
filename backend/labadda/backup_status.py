"""The backup status file: one strict definition shared by the operator tool and the backend.

The operator script (`scripts/lifecycle.py`) writes `backup-status.json` after every scheduled
backup; the backend reads it with `read_status`. The file carries only times, a result, a size,
a verification outcome, a short destination alias, and the schema and release identifiers. It
never holds a path, host name or secret, and every text field is restricted by a pattern that
makes it impossible to smuggle one in. Standard library only, so the stdlib-only operator
script can import it.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

STATUS_FILENAME = "backup-status.json"
FORMAT = 1
# A real file is about 250 bytes; anything near this limit is not ours.
MAX_STATUS_BYTES = 4096
# Same thresholds as the Backups health item (ADMIN-CONSOLE-V1 AD-07).
FRESH_WITHIN = timedelta(hours=26)
STALE_AFTER = timedelta(hours=50)
# Clocks on one host should agree; more than this in the future means the file cannot be trusted.
FUTURE_TOLERANCE = timedelta(minutes=5)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
ALIAS_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,31}")
SCHEMA_PATTERN = re.compile(r"[A-Za-z0-9_]{1,40}")
RELEASE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
MAX_SIZE_BYTES = 2**50

RESULTS = ("success", "failure")
VERIFICATIONS = ("passed", "failed", "not_run")
FIELDS = {
    "format",
    "finished_at",
    "result",
    "size_bytes",
    "verification",
    "destination",
    "schema",
    "release",
}

Result = Literal["success", "failure"]
Verification = Literal["passed", "failed", "not_run"]
ReadState = Literal["unknown", "invalid", "ok"]


class StatusError(ValueError):
    """The status record does not follow the schema."""


@dataclass(frozen=True)
class BackupStatus:
    """One validated backup outcome."""

    finished_at: datetime
    result: Result
    size_bytes: int | None
    verification: Verification
    destination: str
    schema: str | None
    release: str | None

    def as_record(self) -> dict:
        """Return the JSON-ready record, validating it first."""
        record = {
            "format": FORMAT,
            "finished_at": self.finished_at.astimezone(UTC).strftime(TIME_FORMAT),
            "result": self.result,
            "size_bytes": self.size_bytes,
            "verification": self.verification,
            "destination": self.destination,
            "schema": self.schema,
            "release": self.release,
        }
        validate_record(record)
        return record


@dataclass(frozen=True)
class StatusReading:
    """What a reader found: nothing, something unusable, or a valid outcome."""

    state: ReadState
    status: BackupStatus | None = None


def _text(record: dict, name: str, pattern: re.Pattern, *, optional: bool = False) -> str | None:
    value = record[name]
    if value is None and optional:
        return None
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise StatusError(f"Backup status field {name} is not valid")
    return value


def validate_record(record: object) -> BackupStatus:
    """Return the status for a decoded JSON value, or raise StatusError."""
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise StatusError("Backup status must contain exactly the documented fields")
    if record["format"] != FORMAT or isinstance(record["format"], bool):
        raise StatusError("Backup status format is not supported")
    finished_text = _text(record, "finished_at", TIME_PATTERN)
    result = record["result"]
    verification = record["verification"]
    if result not in RESULTS or verification not in VERIFICATIONS:
        raise StatusError("Backup status result or verification is not valid")
    size = record["size_bytes"]
    if size is not None and (type(size) is not int or not 0 <= size <= MAX_SIZE_BYTES):
        raise StatusError("Backup status size is not valid")
    status = BackupStatus(
        finished_at=_parse_time(finished_text),
        result=result,
        size_bytes=size,
        verification=verification,
        destination=_text(record, "destination", ALIAS_PATTERN),
        schema=_text(record, "schema", SCHEMA_PATTERN, optional=True),
        release=_text(record, "release", RELEASE_PATTERN, optional=True),
    )
    _check_consistency(status)
    return status


def _parse_time(text: str) -> datetime:
    try:
        return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError as error:
        raise StatusError("Backup status time is not a real date") from error


def _check_consistency(status: BackupStatus) -> None:
    """A success cannot be unverified or unmeasured; a failure cannot claim verification."""
    if status.result == "success":
        complete = (
            status.verification == "passed"
            and status.size_bytes is not None
            and status.schema is not None
            and status.release is not None
        )
        if not complete:
            raise StatusError("A successful backup must be verified, measured and identified")
    elif status.verification == "passed":
        raise StatusError("A failed backup cannot report a passed verification")


def encode(status: BackupStatus) -> bytes:
    """Return the exact bytes to store for a status."""
    return (json.dumps(status.as_record(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_status(directory: Path, status: BackupStatus) -> None:
    """Replace the status file atomically; an interrupted write leaves the previous file intact.

    The new content is written and flushed to a temporary file in the same directory, then
    renamed over the old one, then the directory entry is flushed. Readers see either the
    complete old file or the complete new file, never a mixture.
    """
    payload = encode(status)
    descriptor, temporary = tempfile.mkstemp(prefix=".backup-status-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        # The runtime account reads this file; it holds no secret.
        os.chmod(temporary, 0o644)
        os.replace(temporary, directory / STATUS_FILENAME)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    directory_descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def read_status(directory: Path | None) -> StatusReading:
    """Read and validate the status file; never raises for a bad or missing file."""
    if directory is None:
        return StatusReading("unknown")
    try:
        descriptor = os.open(directory / STATUS_FILENAME, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return StatusReading("unknown")
    except OSError:
        return StatusReading("invalid")
    try:
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                return StatusReading("invalid")
            content = source.read(MAX_STATUS_BYTES + 1)
    except OSError:
        return StatusReading("invalid")
    if len(content) > MAX_STATUS_BYTES:
        return StatusReading("invalid")
    try:
        return StatusReading("ok", validate_record(json.loads(content)))
    except (ValueError, RecursionError):
        return StatusReading("invalid")


def age(status: BackupStatus, now: datetime) -> timedelta:
    """How long ago the backup finished; negative when the file is dated in the future."""
    return now - status.finished_at
