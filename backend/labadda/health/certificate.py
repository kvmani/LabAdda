"""Certificate: days until the site certificate expires, from the operator status file.

The operator tooling writes ``certificate-status.json`` beside ``backup-status.json``:
``{"format": 1, "checked_at": "<UTC time>", "expires_at": "<UTC time>"}``. Times use the same
``YYYY-MM-DDTHH:MM:SSZ`` form as the backup file. Nothing else is read or shown.
"""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .types import Context, Result, make

STATUS_FILENAME = "certificate-status.json"
MAX_BYTES = 1024
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
FUTURE_TOLERANCE = timedelta(minutes=5)


@dataclass(frozen=True)
class Reading:
    state: str  # "absent", "invalid" or "ok"
    checked_at: datetime | None = None
    expires_at: datetime | None = None


def _time(value: object) -> datetime:
    if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
        raise ValueError("time")
    return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=UTC)


def read(directory: Path | None) -> Reading:
    """Read and validate the file; a missing directory or file is absent, anything else invalid."""
    if directory is None:
        return Reading("absent")
    try:
        descriptor = os.open(directory / STATUS_FILENAME, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return Reading("absent")
    except OSError:
        return Reading("invalid")
    try:
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                return Reading("invalid")
            content = source.read(MAX_BYTES + 1)
        record = json.loads(content) if len(content) <= MAX_BYTES else None
        if not isinstance(record, dict) or set(record) != {"format", "checked_at", "expires_at"}:
            return Reading("invalid")
        if record["format"] != 1 or isinstance(record["format"], bool):
            return Reading("invalid")
        return Reading("ok", _time(record["checked_at"]), _time(record["expires_at"]))
    except (OSError, ValueError, RecursionError):
        return Reading("invalid")


def evaluate(ctx: Context, reading: Reading) -> Result:
    if reading.state == "absent":
        return make(ctx, "unsupported", None, "days", "No certificate report is provided on this instance.")
    if reading.state != "ok" or reading.checked_at is None or reading.expires_at is None:
        return make(ctx, "unknown", None, "days", "The certificate report cannot be read.")
    now = ctx.now()
    limits = ctx.settings.health
    if reading.checked_at - now > FUTURE_TOLERANCE:
        return make(ctx, "unknown", None, "days", "The certificate report is dated in the future.")
    days = (reading.expires_at - now) // timedelta(days=1)
    detail = (
        f"The site certificate expires in {days} days." if days >= 0 else "The site certificate has expired."
    )
    if now - reading.checked_at > timedelta(hours=limits.certificate_fresh_hours):
        return make(ctx, "stale", days, "days", "The certificate was last checked a while ago. " + detail)
    if days < limits.certificate_unavailable_days:
        return make(ctx, "unavailable", days, "days", detail)
    if days < limits.certificate_degraded_days:
        return make(ctx, "degraded", days, "days", detail)
    return make(ctx, "healthy", days, "days", detail)


def check(ctx: Context) -> Result:
    return evaluate(ctx, read(ctx.settings.status_dir))
