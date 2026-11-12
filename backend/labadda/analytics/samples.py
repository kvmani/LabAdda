"""Bounded reads of ``metric_samples`` and ``activity_days`` for one period (AD-05, AD-08).

A period is read from day buckets where the roll-up has made them, then hour buckets after the
newest day, then minute buckets after the newest hour, so no minute is counted twice and the
current day is still included.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, and_, cast, exists, func, select, union_all
from sqlalchemy.orm import Session

from ..models import ActivityDay, MetricSample, User, Workspace
from .periods import Window, midnight

HOUR_RETENTION = timedelta(days=35)


def _latest(db: Session, resolution: str, start: datetime, end: datetime) -> datetime | None:
    return db.scalar(
        select(func.max(MetricSample.bucket_start)).where(
            MetricSample.resolution == resolution,
            MetricSample.bucket_start >= start,
            MetricSample.bucket_start < end,
        )
    )


def _cutoffs(db: Session, window: Window) -> tuple[datetime, datetime]:
    """Where hour buckets take over from days, and minute buckets from hours."""
    latest_day = _latest(db, "day", window.start, window.end)
    day_cut = window.start
    if latest_day is not None:
        local = latest_day.astimezone(ZoneInfo(window.timezone)).date()
        day_cut = midnight(local + timedelta(days=1), window.timezone)
    latest_hour = _latest(db, "hour", day_cut, window.end)
    hour_cut = day_cut if latest_hour is None else latest_hour + timedelta(hours=1)
    return day_cut, hour_cut


def _rows(db: Session, metrics: tuple[str, ...], window: Window, *, with_days: bool = True):
    day_cut, hour_cut = _cutoffs(db, window)
    parts = [("hour", day_cut if with_days else window.start), ("minute", hour_cut)]
    if with_days:
        parts.insert(0, ("day", window.start))
    selects = [
        select(
            MetricSample.bucket_start, MetricSample.metric, MetricSample.dimension, MetricSample.value
        ).where(
            MetricSample.resolution == resolution,
            MetricSample.metric.in_(metrics),
            MetricSample.bucket_start >= lower,
            MetricSample.bucket_start < window.end,
        )
        for resolution, lower in parts
    ]
    return union_all(*selects).subquery()


def site_day(column, timezone: str):
    """The site-local calendar day of a stored UTC instant."""
    return cast(func.timezone(timezone, column), Date)


def daily(
    db: Session, metrics: tuple[str, ...], window: Window, *, peak: bool = False
) -> dict[tuple[date, str, str], float]:
    """Per site-local day, metric and dimension: the sum (counters) or maximum (gauges)."""
    rows = _rows(db, metrics, window)
    day = site_day(rows.c.bucket_start, window.timezone)
    value = func.max(rows.c.value) if peak else func.sum(rows.c.value)
    query = select(day, rows.c.metric, rows.c.dimension, value).group_by(day, rows.c.metric, rows.c.dimension)
    return {(row[0], row[1], row[2]): float(row[3]) for row in db.execute(query)}


def totals(db: Session, metrics: tuple[str, ...], window: Window) -> dict[tuple[str, str], float]:
    """Per metric and dimension, the counter total over the window."""
    rows = _rows(db, metrics, window)
    query = select(rows.c.metric, rows.c.dimension, func.sum(rows.c.value)).group_by(
        rows.c.metric, rows.c.dimension
    )
    return {(row[0], row[1]): float(row[2]) for row in db.execute(query)}


def peak(db: Session, metric: str, window: Window) -> float | None:
    """The highest gauge reading in the window, or None when it was never read."""
    rows = _rows(db, (metric,), window)
    value = db.scalar(select(func.max(rows.c.value)))
    return None if value is None else float(value)


def hour_of_week(db: Session, metric: str, window: Window, *, now: datetime) -> tuple[dict, datetime | None]:
    """Counter totals by site-local ISO weekday (1-7) and hour, over the hours still kept."""
    start = max(window.start, now - HOUR_RETENTION)
    rows = _rows(db, (metric,), window, with_days=False)
    local = func.timezone(window.timezone, rows.c.bucket_start)
    weekday = func.extract("isodow", local)
    hour = func.extract("hour", local)
    query = (
        select(weekday, hour, func.sum(rows.c.value))
        .where(rows.c.bucket_start >= start)
        .group_by(weekday, hour)
    )
    cells = {(int(row[0]), int(row[1])): float(row[2]) for row in db.execute(query)}
    oldest = db.scalar(select(func.min(rows.c.bucket_start)).where(rows.c.bucket_start >= start))
    return cells, oldest


def has_samples(db: Session, window: Window) -> bool:
    """Whether the collector stored anything in the window; nothing stored is unknown, not zero."""
    found = exists().where(MetricSample.bucket_start >= window.start, MetricSample.bucket_start < window.end)
    return bool(db.scalar(select(found)))


def has_activity(db: Session, window: Window) -> bool:
    found = exists().where(ActivityDay.day >= window.first, ActivityDay.day <= window.last)
    return bool(db.scalar(select(found)))


def sampled_days(db: Session, window: Window) -> set[date]:
    """Site-local days on which the collector stored at least one sample."""
    day = site_day(MetricSample.bucket_start, window.timezone)
    query = (
        select(day)
        .where(MetricSample.bucket_start >= window.start, MetricSample.bucket_start < window.end)
        .distinct()
    )
    return set(db.scalars(query))


def active_per_day(db: Session, window: Window) -> dict[date, int]:
    query = (
        select(ActivityDay.day, func.count())
        .where(ActivityDay.day >= window.first, ActivityDay.day <= window.last)
        .group_by(ActivityDay.day)
    )
    return {row[0]: int(row[1]) for row in db.execute(query)}


def active_people(db: Session, window: Window) -> int:
    """Distinct people active on at least one day of the window."""
    return int(
        db.scalar(
            select(func.count(func.distinct(ActivityDay.user_id))).where(
                ActivityDay.day >= window.first, ActivityDay.day <= window.last
            )
        )
    )


def active_by_home_unit(db: Session, window: Window) -> dict[object, int]:
    """Distinct active people per current home organisation unit; None for no org home unit.

    Every person has at most one home, so the groups partition the active people.
    """
    query = (
        select(Workspace.id, func.count(func.distinct(ActivityDay.user_id)))
        .select_from(ActivityDay)
        .join(User, User.id == ActivityDay.user_id)
        .outerjoin(Workspace, and_(Workspace.id == User.home_workspace_id, Workspace.kind == "org"))
        .where(ActivityDay.day >= window.first, ActivityDay.day <= window.last)
        .group_by(Workspace.id)
    )
    return {row[0]: int(row[1]) for row in db.execute(query)}


def enabled_accounts(db: Session) -> int:
    """Accounts that may sign in now: the denominator of "share of active accounts"."""
    return int(db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))))


def people_by_home_unit(db: Session) -> dict[object, int]:
    """Everyone (any status) per current home organisation unit; None for no org home unit."""
    query = (
        select(Workspace.id, func.count(User.id))
        .select_from(User)
        .outerjoin(Workspace, and_(Workspace.id == User.home_workspace_id, Workspace.kind == "org"))
        .group_by(Workspace.id)
    )
    return {row[0]: int(row[1]) for row in db.execute(query)}


def active_per_bucket(db: Session, window: Window, size: str) -> dict[date, int]:
    """Distinct active people per day, ISO week (from Monday) or calendar month of the window."""
    bucket = cast(func.date_trunc(size, ActivityDay.day), Date)
    query = (
        select(bucket, func.count(func.distinct(ActivityDay.user_id)))
        .where(ActivityDay.day >= window.first, ActivityDay.day <= window.last)
        .group_by(bucket)
    )
    return {row[0]: int(row[1]) for row in db.execute(query)}


def active_per_weekday(db: Session, window: Window, since: date) -> dict[int, int]:
    """Distinct active people per ISO weekday (1-7) on days from ``since`` to the window's end."""
    weekday = func.extract("isodow", ActivityDay.day)
    query = (
        select(weekday, func.count(func.distinct(ActivityDay.user_id)))
        .where(ActivityDay.day >= max(since, window.first), ActivityDay.day <= window.last)
        .group_by(weekday)
    )
    return {int(row[0]): int(row[1]) for row in db.execute(query)}
