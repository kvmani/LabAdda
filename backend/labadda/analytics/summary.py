"""Site-wide Activity page figures for one period and the period before it (AD-08).

Everything here is a site total; per-unit figures live in ``units.py`` with small-group
protection. A period in which collection left no trace is ``unknown``, never zero.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..config import Settings
from ..serialize import iso
from . import samples
from .features import CONNECTIONS, FEATURES, ITEM_METRICS, KINDS, REQUESTS, SIZE_LABELS, STORAGE
from .periods import BUCKETS, BucketSize, Window, windows


def _tile(key: str, label: str, unit: str, value: float | None, previous: float | None) -> dict:
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "state": "unknown" if value is None else "measured",
        "value": value,
        "previous": previous,
    }


def _active(db: Session, window: Window | None, days: int | None = None) -> int | None:
    if window is None:
        return None
    return samples.active_people(db, window if days is None else window.tail(days))


def _people_tiles(db: Session, current: Window | None, previous: Window | None) -> list[dict]:
    """People tiles from ``activity_days``; a window without any activity row is unknown."""
    tiles = [
        _tile(key, label, "people", _active(db, current, days), _active(db, previous, days))
        for key, label, days in (
            ("active_day", "Active people on the last day", 1),
            ("active_week", "Active people in the last 7 days", 7),
            ("active_month", "Active people in the last 30 days", 30),
        )
    ]
    accounts = samples.enabled_accounts(db)
    active = _active(db, current)
    before = _active(db, previous)
    share = active / accounts if accounts and active is not None else None
    before_share = before / accounts if accounts and before is not None else None
    tile = _tile("active_share", "Share of accounts active in the period", "fraction", share, before_share)
    tiles.append({**tile, "active": active, "accounts": accounts})
    return tiles


def _items(db: Session, window: Window) -> float:
    found = samples.totals(db, ITEM_METRICS, window)
    return sum(value for (_, dimension), value in found.items() if dimension in dict(KINDS))


def _bucket(day: date, size: BucketSize) -> date:
    if size == "week":
        return day - timedelta(days=day.weekday())
    if size == "month":
        return day.replace(day=1)
    return day


def _features(db: Session, window: Window, size: BucketSize, sampled: set[date]) -> dict:
    """Stacked feature counts per bucket; a bucket with no measured day has null values."""
    kinds = dict(KINDS)
    daily = samples.daily(db, tuple(metric for metric, _ in FEATURES), window)
    starts = sorted({_bucket(window.first + timedelta(days=n), size) for n in range(window.days)})
    sums: dict[date, dict[str, float]] = {start: {} for start in starts}
    for (day, metric, dimension), value in daily.items():
        if dimension in kinds:
            values = sums[_bucket(day, size)]
            values[metric] = values.get(metric, 0.0) + value
    seen = {_bucket(day, size) for day in sampled}
    points = [
        {
            "start": start.isoformat(),
            "values": {metric: sums[start].get(metric, 0.0) for metric, _ in FEATURES}
            if start in seen
            else None,
        }
        for start in starts
    ]
    return {
        "bucket": size,
        "series": [{"key": key, "label": label} for key, label in FEATURES],
        "points": points,
    }


def _by_kind(db: Session, window: Window) -> list[dict]:
    found = samples.totals(db, ITEM_METRICS, window)
    return [
        {"key": key, "label": label, "value": sum(v for (_, dim), v in found.items() if dim == key)}
        for key, label in KINDS
    ]


def _heat(db: Session, window: Window, now: datetime) -> dict:
    cells, oldest = samples.hour_of_week(db, REQUESTS, window, now=now)
    if oldest is None:
        return {"state": "unknown", "from": None, "cells": []}
    grid = [
        {"weekday": weekday, "hour": hour, "value": cells.get((weekday, hour), 0.0)}
        for weekday in range(1, 8)
        for hour in range(24)
    ]
    return {"state": "measured", "from": iso(oldest), "cells": grid}


def _storage(db: Session, window: Window) -> list[dict]:
    daily = samples.daily(db, tuple(metric for metric, _ in STORAGE), window, peak=True)
    days = sorted({day for day, _, _ in daily})
    names = dict(STORAGE)
    points = []
    for day in days:
        point: dict[str, object] = {"day": day.isoformat()}
        for metric, name in names.items():
            point[f"{name}_bytes"] = daily.get((day, metric, ""))
        points.append(point)
    return points


def _upload_sizes(db: Session, window: Window) -> list[dict]:
    found = samples.totals(db, ("uploads.size_band",), window)
    return [
        {"key": band, "label": label, "value": found.get(("uploads.size_band", band), 0.0)}
        for band, label in SIZE_LABELS.items()
    ]


def _charts(db: Session, window: Window, period: str, now: datetime) -> dict:
    sampled = samples.sampled_days(db, window)
    active = samples.active_per_day(db, window)
    days = [window.first + timedelta(days=n) for n in range(window.days)]
    # A day with samples but no activity row is a measured zero; a day with neither is a gap.
    measured = sampled | set(active)
    return {
        "active_per_day": [
            {"day": day.isoformat(), "value": active.get(day, 0) if day in measured else None} for day in days
        ],
        "features": _features(db, window, BUCKETS[period], sampled),
        "items_by_kind": _by_kind(db, window),
        "weekday_hour": _heat(db, window, now),
        "storage": _storage(db, window),
        "upload_sizes": _upload_sizes(db, window),
    }


def build_summary(db: Session, settings: Settings, period: str, *, now: datetime) -> dict:
    current, previous = windows(period, settings, now=now)
    payload = {
        "period": period,
        "timezone": settings.timezone,
        "generated_at": iso(now),
        "current": current.json(),
        "previous": previous.json(),
    }
    people_now = samples.has_activity(db, current)
    sampled_now = samples.has_samples(db, current)
    if not people_now and not sampled_now:
        return {**payload, "state": "unknown", "tiles": [], "charts": None}
    people_before = previous if samples.has_activity(db, previous) else None
    sampled_before = previous if samples.has_samples(db, previous) else None
    tiles = [
        *_people_tiles(db, current if people_now else None, people_before),
        _tile(
            "peak_connections",
            "Peak simultaneous connections",
            "connections",
            samples.peak(db, CONNECTIONS, current),
            samples.peak(db, CONNECTIONS, sampled_before) if sampled_before else None,
        ),
        _tile(
            "items_created",
            "Items created",
            "items",
            _items(db, current) if sampled_now else None,
            _items(db, sampled_before) if sampled_before else None,
        ),
    ]
    return {**payload, "state": "measured", "tiles": tiles, "charts": _charts(db, current, period, now)}
