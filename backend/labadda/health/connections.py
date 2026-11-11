"""Live connections: connected sockets, recent sessions and the delivery backlog."""

from __future__ import annotations

from ..metrics import gauges
from .types import Context, Result, make

UNAVAILABLE_FACTOR = 5  # backlog this many times its bound is unavailable


def evaluate(ctx: Context, *, sockets: int, sessions: int, backlog: int) -> Result:
    bound = ctx.settings.health.queue_backlog
    detail = f"{sessions} signed-in sessions seen in the last 5 minutes; {backlog} messages waiting."
    if backlog > bound * UNAVAILABLE_FACTOR:
        return make(ctx, "unavailable", sockets, "connections", "Live delivery is far behind. " + detail)
    if backlog > bound:
        return make(ctx, "degraded", sockets, "connections", "Live delivery is falling behind. " + detail)
    return make(ctx, "healthy", sockets, "connections", detail)


def check(ctx: Context) -> Result:
    sockets = ctx.sockets()
    try:
        with ctx.factory() as db:
            sessions = gauges.active_sessions(db, ctx.now())
    except Exception:  # noqa: BLE001 — the session count needs the database; sockets still show
        return make(ctx, "unknown", sockets, "connections", "Signed-in sessions could not be counted.")
    return evaluate(ctx, sockets=sockets, sessions=sessions, backlog=ctx.backlog())
