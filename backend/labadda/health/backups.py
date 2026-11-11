"""Backups: age and verification of the latest backup receipt (AD-10)."""

from __future__ import annotations

from datetime import timedelta

from .. import backup_status
from .types import Context, Result, human_duration, make


def evaluate(ctx: Context, reading: backup_status.StatusReading) -> Result:
    if reading.state == "unknown":
        return make(
            ctx, "unknown", None, "hours", "No backup report was found, so backups are not confirmed."
        )
    status = reading.status
    if reading.state == "invalid" or status is None:
        return make(ctx, "unknown", None, "hours", "The backup report cannot be read.")
    now = ctx.now()
    age = backup_status.age(status, now)
    if age < -backup_status.FUTURE_TOLERANCE:
        return make(ctx, "unknown", None, "hours", "The backup report is dated in the future.")
    limits = ctx.settings.health
    hours = round(max(age, timedelta(0)).total_seconds() / 3600, 1)
    when = f"The last backup finished {human_duration(max(age.total_seconds(), 0))} ago."
    if status.result == "failure" or status.verification == "failed":
        return make(ctx, "unavailable", hours, "hours", "The last backup failed or did not verify. " + when)
    if age > timedelta(hours=limits.backup_stale_hours):
        return make(ctx, "unavailable", hours, "hours", "No recent backup exists. " + when)
    if age > timedelta(hours=limits.backup_fresh_hours):
        return make(ctx, "degraded", hours, "hours", "The latest backup is older than expected. " + when)
    return make(ctx, "healthy", hours, "hours", when + " It was checked after it was made.")


def check(ctx: Context) -> Result:
    return evaluate(ctx, backup_status.read_status(ctx.settings.status_dir))
