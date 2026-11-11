"""Database: round-trip time, connections used of the maximum, and database size."""

from __future__ import annotations

import time

from sqlalchemy import text

from .types import Context, Result, human_bytes, make


def evaluate(ctx: Context, *, round_trip_ms: float, used: int, maximum: int, size: int) -> Result:
    limits = ctx.settings.health
    percent = used * 100 / maximum if maximum else 0
    detail = f"{used} of {maximum} connections in use; database size {human_bytes(size)}."
    problems = []
    if round_trip_ms > limits.db_slow_ms:
        problems.append(f"Answers are slow ({round(round_trip_ms)} ms).")
    if percent > limits.db_connections_percent:
        problems.append(f"{round(percent)} % of the connections are in use.")
    status = "degraded" if problems else "healthy"
    return make(ctx, status, round(round_trip_ms, 1), "ms", " ".join([*problems, detail]))


def check(ctx: Context) -> Result:
    try:
        with ctx.factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            started = time.perf_counter()
            db.execute(text("select 1"))
            round_trip = (time.perf_counter() - started) * 1000
            used = db.scalar(text("select count(*) from pg_stat_activity"))
            maximum = int(db.scalar(text("show max_connections")))
            size = db.scalar(text("select pg_database_size(current_database())"))
    except Exception:  # noqa: BLE001 — any failure to answer means the database is unreachable
        return make(ctx, "unavailable", None, "ms", "The database does not answer.")
    return evaluate(ctx, round_trip_ms=round_trip, used=used, maximum=maximum, size=size)
