"""Application: version, uptime, and whether the database schema is the one this release expects."""

from __future__ import annotations

from sqlalchemy import text

from .. import __version__
from .types import Context, Result, human_duration, make


def evaluate(ctx: Context, *, uptime: float, current: str | None, expected: str) -> Result:
    summary = f"Version {__version__}, running for {human_duration(uptime)}."
    if current == expected:
        return make(ctx, "healthy", round(uptime), "seconds", f"{summary} The database layout matches.")
    side = "behind" if (current or "") < expected else "ahead of"
    return make(
        ctx,
        "degraded",
        round(uptime),
        "seconds",
        f"{summary} The database layout is {side} this release; finish the upgrade or switch back.",
    )


def check(ctx: Context) -> Result:
    try:
        with ctx.factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            current = db.scalar(text("select version_num from alembic_version"))
    except Exception:  # noqa: BLE001 — the Database item reports the outage; this one cannot tell
        return make(ctx, "unknown", None, "seconds", "The database layout could not be read.")
    uptime = (ctx.now() - ctx.started).total_seconds()
    return evaluate(ctx, uptime=uptime, current=current, expected=ctx.expected_schema())
