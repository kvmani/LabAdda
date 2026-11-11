"""The Backups page payload (AD-10): what the operator's status file says, in console words.

The page never implies that backups exist: a missing, oversized or malformed file is `unknown`
with guidance. Nothing from the file other than the schema's own short fields is returned, so
no path, host name or secret can reach the browser.
"""

from __future__ import annotations

from datetime import datetime

from . import backup_status
from .config import Settings

SETUP_GUIDE = "docs/OPERATOR-QUICKSTART.md"
HOURS = 3600


def _unknown(headline: str, guidance: str) -> dict:
    return {"status": "unknown", "headline": headline, "guidance": guidance, "last_backup": None}


def _classify(status: backup_status.BackupStatus, now: datetime) -> tuple[str, str, str | None]:
    """Return the AD-03 word, a plain headline and guidance for a validated receipt."""
    elapsed = backup_status.age(status, now)
    if elapsed < -backup_status.FUTURE_TOLERANCE:
        return (
            "unknown",
            "The last backup is dated in the future.",
            "Ask the person who looks after the server to check the computer's clock.",
        )
    if status.result != "success" or status.verification == "failed":
        return (
            "unavailable",
            "The last backup did not complete or could not be verified.",
            "Ask the person who looks after the server to read the backup log and run it again.",
        )
    if elapsed > backup_status.STALE_AFTER:
        return (
            "stale",
            "The last good backup is more than 50 hours old.",
            "Ask the person who looks after the server to check the backup timer.",
        )
    if elapsed > backup_status.FRESH_WITHIN:
        return (
            "degraded",
            "The last good backup is more than 26 hours old.",
            "Ask the person who looks after the server to check that the nightly backup ran.",
        )
    return "healthy", "The last backup finished and was verified.", None


def backup_report(settings: Settings, now: datetime) -> dict:
    """Return the page payload; never raises for a bad status file."""
    reading = backup_status.read_status(settings.status_dir)
    if reading.status is None:
        if reading.state == "invalid":
            report = _unknown(
                "The backup record cannot be read.",
                "The record may have been edited or damaged. Ask the person who looks after the "
                "server to run a backup again.",
            )
        else:
            report = _unknown(
                "No backup has been recorded.",
                "Backups are set up on the server, not in this application. Ask the person who "
                "looks after the server to follow the set-up guide.",
            )
    else:
        status = reading.status
        word, headline, guidance = _classify(status, now)
        report = {
            "status": word,
            "headline": headline,
            "guidance": guidance,
            "last_backup": {
                "finished_at": status.finished_at.isoformat().replace("+00:00", "Z"),
                "age_seconds": max(0, int(backup_status.age(status, now).total_seconds())),
                "result": status.result,
                "size_bytes": status.size_bytes,
                "verification": status.verification,
                "destination": status.destination,
                "schema": status.schema,
                "release": status.release,
            },
        }
    return {
        **report,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "healthy_within_hours": int(backup_status.FRESH_WITHIN.total_seconds() // HOURS),
        "stale_after_hours": int(backup_status.STALE_AFTER.total_seconds() // HOURS),
        # The status file carries neither; the page says "not recorded" rather than guessing.
        "next_run": None,
        "restore_rehearsal": None,
        "setup_guide": SETUP_GUIDE,
    }
