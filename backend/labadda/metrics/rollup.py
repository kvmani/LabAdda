"""Roll minutes into site-local hours and hours into site-local days; delete expired rows.

Every roll-up recomputes whole target buckets from their source rows and replaces them, so
running it twice, or after a crash midway, gives the same result. Hours are site-local
hours (in a +05:30 zone they start at :30 UTC) so that they nest exactly inside site days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import ActivityDay, MetricSample
from ..people import site_date
from . import catalog
from .flush import upsert
from .registry import Sample


@dataclass(frozen=True)
class Step:
    """One roll-up level: source resolution, target resolution and the date_trunc field."""

    source: str
    target: str
    field: str


STEPS = (Step("minute", "hour", "hour"), Step("hour", "day", "day"))


def _truncate(db: Session, field: str, instant: datetime, timezone: str) -> datetime:
    return db.scalar(select(func.date_trunc(field, instant, timezone)))


def _first_bucket(db: Session, step: Step, timezone: str) -> datetime | None:
    # Recompute the newest target bucket again: it may have been rolled before its source
    # rows were complete. Without targets yet, start at the oldest source bucket.
    latest = db.scalar(
        select(func.max(MetricSample.bucket_start)).where(MetricSample.resolution == step.target)
    )
    if latest is not None:
        return latest
    oldest = db.scalar(
        select(func.min(MetricSample.bucket_start)).where(MetricSample.resolution == step.source)
    )
    return None if oldest is None else _truncate(db, step.field, oldest, timezone)


def _combine(metric: str, total: float, peak: float, weighted: float, samples: int) -> float:
    kind = catalog.series_metric(metric).kind
    if kind == "counter":
        return total
    if kind == "gauge":
        # Peaks matter for capacity and "peak simultaneous connections".
        return peak
    # Exact percentiles cannot be merged; use the request-weighted mean of the parts.
    return weighted / samples if samples else 0.0


def roll_step(db: Session, step: Step, *, timezone: str, now: datetime) -> int:
    """Recompute complete target buckets that may have changed; the caller commits."""
    start = _first_bucket(db, step, timezone)
    end = _truncate(db, step.field, now, timezone)
    if start is None or start >= end:
        return 0
    bucket = func.date_trunc(step.field, MetricSample.bucket_start, timezone).label("bucket")
    rows = db.execute(
        select(
            bucket,
            MetricSample.metric,
            MetricSample.dimension,
            func.sum(MetricSample.value),
            func.max(MetricSample.value),
            func.sum(MetricSample.value * MetricSample.samples),
            func.sum(MetricSample.samples),
        )
        .where(
            MetricSample.resolution == step.source,
            MetricSample.bucket_start >= start,
            MetricSample.bucket_start < end,
        )
        .group_by(bucket, MetricSample.metric, MetricSample.dimension)
    ).all()
    samples = [
        Sample(row[0], row[1], row[2], _combine(row[1], row[3], row[4], row[5], int(row[6])), int(row[6]))
        for row in rows
        if row[1] in catalog.SERIES
    ]
    return upsert(db, step.target, samples)


def expire(db: Session, settings: Settings, *, now: datetime) -> None:
    """Delete samples and activity days past their retention; the caller commits."""
    limits = {
        "minute": timedelta(hours=settings.metrics_minute_retention_hours),
        "hour": timedelta(days=settings.metrics_hour_retention_days),
        "day": timedelta(days=settings.metrics_day_retention_days),
    }
    for resolution, keep in limits.items():
        db.execute(
            delete(MetricSample).where(
                MetricSample.resolution == resolution, MetricSample.bucket_start < now - keep
            )
        )
    oldest_day = site_date(settings, now=now) - timedelta(days=settings.activity_retention_days)
    db.execute(delete(ActivityDay).where(ActivityDay.day < oldest_day))


def roll_up(db: Session, settings: Settings, *, now: datetime) -> None:
    """Roll every level, then apply retention, in one transaction."""
    for step in STEPS:
        roll_step(db, step, timezone=settings.timezone, now=now)
        db.flush()
    expire(db, settings, now=now)
    db.commit()
