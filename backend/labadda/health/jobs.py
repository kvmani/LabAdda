"""Background jobs: time since the scheduler last finished a pass, and failed runs in the last hour."""

from __future__ import annotations

from .types import Context, Result, human_duration, make


def evaluate(ctx: Context, *, quiet_seconds: float, ticked: bool, failures: int) -> Result:
    limits = ctx.settings.health
    quiet = round(quiet_seconds)
    detail = f"{failures} failed runs in the last hour."
    if quiet_seconds > limits.job_stall_unavailable_seconds:
        message = f"The scheduler has not finished a pass for {human_duration(quiet)}. "
        return make(ctx, "unavailable", quiet, "seconds", message + detail)
    if quiet_seconds > limits.job_stall_degraded_seconds:
        message = f"The scheduler is running late ({human_duration(quiet)} since its last pass). "
        return make(ctx, "degraded", quiet, "seconds", message + detail)
    if not ticked:
        return make(ctx, "unknown", None, "seconds", "The scheduler has not finished its first pass yet.")
    if failures >= limits.job_failures_per_hour:
        return make(ctx, "degraded", quiet, "seconds", "Scheduled work keeps failing. " + detail)
    return make(ctx, "healthy", quiet, "seconds", f"Last pass finished {human_duration(quiet)} ago. {detail}")


def check(ctx: Context) -> Result:
    if not ctx.settings.run_scheduler:
        return make(ctx, "unsupported", None, "seconds", "The scheduler is turned off on this instance.")
    now = ctx.now()
    last = ctx.heartbeat.last_tick()
    quiet = (now - (last or ctx.started)).total_seconds()
    failures = ctx.heartbeat.failures_in_last_hour(now)
    return evaluate(ctx, quiet_seconds=quiet, ticked=last is not None, failures=failures)
