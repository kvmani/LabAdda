"""Site-wide Activity page figures for one period and the period before it (AD-08).

Everything here is a site total; per-unit figures live in ``units.py``. A period in which
collection left no trace is ``unknown``, never zero, and a people figure (or one that rests on
fewer than five active people) is ``suppressed`` below five, so a very small site cannot show
one person's activity.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..config import Settings
from ..serialize import iso
from . import samples
from .charts import build_charts, state
from .features import CONNECTIONS, ITEM_METRICS, KINDS
from .periods import Window, windows

Reading = tuple[float | None, str]
UNKNOWN: Reading = (None, "unknown")


def _tile(key: str, label: str, unit: str, current: Reading, previous: Reading) -> dict:
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "state": current[1],
        "value": current[0],
        "previous_state": previous[1],
        "previous": previous[0],
    }


def _people(db: Session, window: Window | None, days: int | None = None) -> Reading:
    """Distinct active people in a window (or its last ``days``), floored at five."""
    if window is None:
        return UNKNOWN
    count = samples.active_people(db, window if days is None else window.tail(days))
    word = state(count, True)
    return (count if word == "measured" else None, word)


def _share(reading: Reading, accounts: int) -> Reading:
    value, word = reading
    if word != "measured" or not accounts or value is None:
        return (None, word if accounts else "unknown")
    return (value / accounts, word)


def _people_tiles(db: Session, current: Window | None, previous: Window | None) -> list[dict]:
    """People tiles from ``activity_days``; a window without any activity row is unknown."""
    tiles = [
        _tile(key, label, "people", _people(db, current, days), _people(db, previous, days))
        for key, label, days in (
            ("active_day", "Active people on the last day", 1),
            ("active_week", "Active people in the last 7 days", 7),
            ("active_month", "Active people in the last 30 days", 30),
        )
    ]
    accounts = samples.enabled_accounts(db)
    active = _people(db, current)
    tile = _tile(
        "active_share",
        "Share of accounts active in the period",
        "fraction",
        _share(active, accounts),
        _share(_people(db, previous), accounts),
    )
    tiles.append({**tile, "active": active[0], "accounts": accounts})
    return tiles


def _items(db: Session, window: Window | None) -> Reading:
    """Items created, suppressed when fewer than five people were active in the window."""
    if window is None:
        return UNKNOWN
    word = state(samples.active_people(db, window), True)
    if word != "measured":
        return (None, word)
    found = samples.totals(db, ITEM_METRICS, window)
    return (sum(value for (_, dimension), value in found.items() if dimension in dict(KINDS)), word)


def _peak(db: Session, window: Window | None) -> Reading:
    value = samples.peak(db, CONNECTIONS, window) if window else None
    return (value, "unknown" if value is None else "measured")


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
            _peak(db, current),
            _peak(db, sampled_before),
        ),
        _tile(
            "items_created",
            "Items created",
            "items",
            _items(db, current if sampled_now else None),
            _items(db, sampled_before),
        ),
    ]
    site_people = samples.active_people(db, current)
    charts = build_charts(db, current, period, now, site_people)
    return {**payload, "state": "measured", "tiles": tiles, "charts": charts}
