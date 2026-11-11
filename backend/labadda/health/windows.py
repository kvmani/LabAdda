"""Closed metric minutes of the last few minutes: stored rows plus those not yet flushed."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, text

from ..metrics.registry import minute_of
from ..models import MetricSample
from .types import Context

Rows = dict[tuple, tuple[float, int]]


def recent_minutes(ctx: Context, minutes: int, metrics: set[str]) -> Rows:
    """Rows keyed by (minute, metric, dimension) -> (value, samples), newest closed minute last.

    The open minute is left out because its totals are still changing. A minute that is both stored
    and still in memory (a flush between commit and discard) is counted once, from memory.
    """
    now = ctx.now()
    end = minute_of(now)
    start = end - timedelta(minutes=minutes)
    rows: Rows = {}
    with ctx.factory() as db:
        db.execute(text("set local statement_timeout = '2s'"))
        for row in db.scalars(
            select(MetricSample).where(
                MetricSample.resolution == "minute",
                MetricSample.metric.in_(metrics),
                MetricSample.bucket_start >= start,
                MetricSample.bucket_start < end,
            )
        ):
            rows[(row.bucket_start, row.metric, row.dimension)] = (row.value, row.samples)
    for sample in ctx.registry.closed(now):
        if sample.metric in metrics and start <= sample.bucket_start < end:
            rows[(sample.bucket_start, sample.metric, sample.dimension)] = (sample.value, sample.samples)
    return rows


def total(rows: Rows, metric: str, dimension: str | None = None) -> float:
    return sum(
        value for (_, name, dim), (value, _) in rows.items() if name == metric and dimension in (None, dim)
    )


def weighted_mean(rows: Rows, metric: str, dimension: str) -> float | None:
    """Request-weighted mean of per-minute percentiles, the same approximation the roll-up uses."""
    parts = [
        (value, samples)
        for (_, name, dim), (value, samples) in rows.items()
        if name == metric and dim == dimension
    ]
    weight = sum(samples for _, samples in parts)
    return sum(value * samples for value, samples in parts) / weight if weight else None
