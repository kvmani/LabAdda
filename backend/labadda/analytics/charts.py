"""The site-wide charts of the Activity page, with the small-group floor applied (AD-08).

A site total could still be one person's activity on a very small site, or on a quiet day of a
larger one. So a day, chart bucket or weekday on which fewer than ``MIN_GROUP`` people were
active is ``suppressed`` (sent without numbers), and the item totals are suppressed when fewer
than ``MIN_GROUP`` people were active in the whole period.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..serialize import iso
from . import samples
from .features import FEATURES, ITEM_METRICS, KINDS, REQUESTS, SIZE_LABELS, STORAGE
from .periods import BUCKETS, BucketSize, Window
from .protect import MIN_GROUP


def state(people: int | None, measured: bool) -> str:
    """``unknown`` without data; ``suppressed`` when fewer than five people stand behind it."""
    if not measured or people is None:
        return "unknown"
    return "suppressed" if people < MIN_GROUP else "measured"


def bucket_of(day: date, size: BucketSize) -> date:
    if size == "week":
        return day - timedelta(days=day.weekday())
    if size == "month":
        return day.replace(day=1)
    return day


def _features(db: Session, window: Window, size: BucketSize, sampled: set[date]) -> dict:
    """Stacked feature counts per bucket; values are null unless the bucket is ``measured``."""
    kinds = dict(KINDS)
    daily = samples.daily(db, tuple(metric for metric, _ in FEATURES), window)
    starts = sorted({bucket_of(window.first + timedelta(days=n), size) for n in range(window.days)})
    sums: dict[date, dict[str, float]] = {start: {} for start in starts}
    for (day, metric, dimension), value in daily.items():
        if dimension in kinds:
            values = sums[bucket_of(day, size)]
            values[metric] = values.get(metric, 0.0) + value
    seen = {bucket_of(day, size) for day in sampled}
    people = samples.active_per_bucket(db, window, size)
    points = []
    for start in starts:
        word = state(people.get(start, 0), start in seen)
        values = {metric: sums[start].get(metric, 0.0) for metric, _ in FEATURES}
        points.append(
            {"start": start.isoformat(), "state": word, "values": values if word == "measured" else None}
        )
    series = [{"key": key, "label": label} for key, label in FEATURES]
    return {"bucket": size, "series": series, "points": points}


def _totals(found: dict[tuple[str, str], float], metric: str | None, keys, word: str) -> list[dict]:
    rows = []
    for key, label in keys:
        value = sum(v for (name, dim), v in found.items() if dim == key and metric in (None, name))
        rows.append(
            {"key": key, "label": label, "state": word, "value": value if word == "measured" else None}
        )
    return rows


def _heat(db: Session, window: Window, now: datetime) -> dict:
    cells, oldest = samples.hour_of_week(db, REQUESTS, window, now=now)
    if oldest is None:
        return {"state": "unknown", "from": None, "cells": [], "suppressed_weekdays": []}
    since = oldest.astimezone(ZoneInfo(window.timezone)).date()
    people = samples.active_per_weekday(db, window, since)
    hidden = [weekday for weekday in range(1, 8) if people.get(weekday, 0) < MIN_GROUP]
    grid = [
        {
            "weekday": weekday,
            "hour": hour,
            "value": None if weekday in hidden else cells.get((weekday, hour), 0.0),
        }
        for weekday in range(1, 8)
        for hour in range(24)
    ]
    word = "suppressed" if len(hidden) == 7 else "measured"
    return {"state": word, "from": iso(oldest), "cells": grid, "suppressed_weekdays": hidden}


def _storage(db: Session, window: Window) -> list[dict]:
    daily = samples.daily(db, tuple(metric for metric, _ in STORAGE), window, peak=True)
    points = []
    for day in sorted({day for day, _, _ in daily}):
        point: dict[str, object] = {"day": day.isoformat()}
        for metric, name in STORAGE:
            point[f"{name}_bytes"] = daily.get((day, metric, ""))
        points.append(point)
    return points


def build_charts(db: Session, window: Window, period: str, now: datetime, site_people: int) -> dict:
    sampled = samples.sampled_days(db, window)
    active = samples.active_per_day(db, window)
    days = [window.first + timedelta(days=n) for n in range(window.days)]
    # A day with samples but no activity row is a measured zero; a day with neither is a gap.
    measured = sampled | set(active)
    per_day = []
    for day in days:
        word = state(active.get(day, 0), day in measured)
        per_day.append(
            {"day": day.isoformat(), "state": word, "value": active[day] if word == "measured" else None}
        )
    floor = state(site_people, bool(sampled))
    items = samples.totals(db, ITEM_METRICS, window)
    sizes = samples.totals(db, ("uploads.size_band",), window)
    return {
        "active_per_day": per_day,
        "features": _features(db, window, BUCKETS[period], sampled),
        "items_by_kind": _totals(items, None, KINDS, floor),
        "weekday_hour": _heat(db, window, now),
        "storage": _storage(db, window),
        "upload_sizes": _totals(sizes, "uploads.size_band", SIZE_LABELS.items(), floor),
    }
