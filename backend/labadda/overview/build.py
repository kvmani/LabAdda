"""Assemble the Overview payload from the cheap sources the console already keeps (AD-05)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .. import analytics
from ..analytics.periods import windows
from ..config import Settings
from ..health.types import worst
from ..serialize import iso
from . import attention, tiles


def build_overview(db: Session, settings: Settings, health_items: list[dict], *, now: datetime) -> dict:
    """Metadata only: statuses, counts, sizes, times and unit names."""
    window, _ = windows("7d", settings, now=now)
    # The same cached 7-day summary the Activity page serves, so the floor is applied once.
    summary = analytics.CACHE.get(
        ("summary", "7d", settings.timezone),
        lambda: analytics.build_summary(db, settings, "7d", now=now),
    )
    health = {item["key"]: item for item in health_items}
    events = attention.open_events(db)
    listed = attention.health_entries(health_items)
    entries = attention.ordered(
        [
            *listed,
            *attention.event_entries(events, {entry["id"].split(":", 1)[1] for entry in listed}),
            *attention.people_entries(db, settings, now),
        ]
    )
    return {
        "generated_at": iso(now),
        "timezone": settings.timezone,
        "period": window.json(),
        "overall": worst([item["status"] for item in health_items]),
        "attention": entries,
        "tiles": tiles.build_tiles(db, settings, window, summary, health=health, now=now),
        "charts": tiles.build_charts(db, window, summary),
    }
