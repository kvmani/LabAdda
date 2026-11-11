"""Sign-in: successful and failed sign-ins over 15 minutes, and a spike in failures."""

from __future__ import annotations

from . import windows
from .types import Context, Result, make

WINDOW_MINUTES = 15
# Too few attempts to call a rate a spike.
MIN_ATTEMPTS = 10
METRICS = {"auth.signin_ok", "auth.signin_failed"}


def evaluate(ctx: Context, *, succeeded: float, failed: float) -> Result:
    attempts = succeeded + failed
    detail = f"{round(succeeded)} signed in and {round(failed)} failed in the last 15 minutes."
    if not attempts:
        return make(ctx, "healthy", 0, "failed sign-ins", "Nobody tried to sign in in the last 15 minutes.")
    percent = failed * 100 / attempts
    if attempts >= MIN_ATTEMPTS and percent > ctx.settings.health.signin_failure_percent:
        return make(ctx, "degraded", round(failed), "failed sign-ins", "Many sign-ins are failing. " + detail)
    return make(ctx, "healthy", round(failed), "failed sign-ins", detail)


def check(ctx: Context) -> Result:
    try:
        rows = windows.recent_minutes(ctx, WINDOW_MINUTES, METRICS)
    except Exception:  # noqa: BLE001 — stored minutes need the database
        return make(ctx, "unknown", None, "failed sign-ins", "Recent sign-ins could not be read.")
    return evaluate(
        ctx, succeeded=windows.total(rows, "auth.signin_ok"), failed=windows.total(rows, "auth.signin_failed")
    )
