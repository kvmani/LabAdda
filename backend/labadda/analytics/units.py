"""Activity by organisation unit with small-group protection (AD-08 "activity by unit").

Projects and groups never appear here: they are reported only as the totals "Projects" and
"Groups" in the summary.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..metrics import catalog
from ..models import Workspace
from ..serialize import iso
from . import protect, samples
from .features import ITEM_METRICS
from .periods import Window, windows

CHART_UNITS = 10


OVERFLOW = "overflow"


def _items_by_unit(db: Session, window: Window) -> dict[object, float]:
    """Items per organisation unit (by id) and in the overflow bucket, as in the org total."""
    found: dict[object, float] = {}
    for (_, dimension), value in samples.totals(db, ITEM_METRICS, window).items():
        if dimension == catalog.UNIT_OVERFLOW:
            key: object = OVERFLOW
        elif catalog.is_unit_dimension(dimension):
            key = uuid.UUID(dimension[len(catalog.UNIT_PREFIX) :])
        else:
            continue
        found[key] = found.get(key, 0.0) + value
    return found


def _item_figures(
    db: Session, window: Window, keys: list[uuid.UUID | None], people_shown: set
) -> dict[uuid.UUID | None, dict | None]:
    """Each unit's published item count; people without a home unit have no space of their own."""
    if not samples.has_samples(db, window):
        return {key: None if key is None else _unknown_or_hidden(key in people_shown) for key in keys}
    items = _items_by_unit(db, window)
    every = {key: items.get(key, 0.0) for key in keys if key is not None}
    every.update({key: value for key, value in items.items() if key not in every})
    shown = protect.published_items(every, people_shown)
    return {key: None if key is None else protect.figure(every[key], key in shown) for key in keys}


def _unknown_or_hidden(visible: bool) -> dict:
    return {"state": "unknown"} if visible else {"state": "suppressed"}


def _figures(
    db: Session, window: Window, keys: list[uuid.UUID | None], headcount: dict
) -> dict[uuid.UUID | None, dict]:
    """Each row's published figures for one window; suppression is decided on exact values."""
    active = samples.active_by_home_unit(db, window)
    at_risk = {key: active.get(key, 0) for key in keys if headcount.get(key, 0) > 0}
    shown = protect.published(at_risk)
    items = _item_figures(db, window, keys, shown)
    return {
        key: {"active_people": protect.figure(active.get(key, 0), key in shown), "items_created": items[key]}
        for key in keys
    }


def _chart(rows: list[dict]) -> list[dict]:
    """Top units by published active people plus "Other units"; suppressed rows are left out."""
    shown = [row for row in rows if row["id"] and row["active_people"]["state"] == "shown"]
    shown.sort(key=lambda row: (-row["active_people"]["value"], row["name"]))
    bars = [{"label": row["name"], "value": row["active_people"]["value"]} for row in shown[:CHART_UNITS]]
    rest = shown[CHART_UNITS:]
    if rest:
        bars.append({"label": "Other units", "value": sum(row["active_people"]["value"] for row in rest)})
    return bars


def build_units(db: Session, settings: Settings, period: str, *, now: datetime) -> dict:
    current, previous = windows(period, settings, now=now)
    payload = {
        "period": period,
        "timezone": settings.timezone,
        "generated_at": iso(now),
        "current": current.json(),
        "previous": previous.json(),
        "minimum_group": protect.MIN_GROUP,
        "rounded_to": protect.ROUND_TO,
    }
    if not samples.has_activity(db, current):
        return {**payload, "state": "unknown", "units": [], "no_home_unit": None, "chart": []}
    units = db.execute(
        select(Workspace.id, Workspace.name, Workspace.parent_id, Workspace.archived)
        .where(Workspace.kind == "org")
        .order_by(Workspace.name, Workspace.id)
    ).all()
    keys: list[uuid.UUID | None] = [unit.id for unit in units] + [None]
    headcount = samples.people_by_home_unit(db)
    now_figures = _figures(db, current, keys, headcount)
    before = _figures(db, previous, keys, headcount) if samples.has_activity(db, previous) else None

    def row(key: uuid.UUID | None) -> dict:
        return {
            **now_figures[key],
            "previous_active_people": before[key]["active_people"] if before else None,
        }

    rows = [
        {
            "id": str(unit.id),
            "name": unit.name,
            "parent_id": str(unit.parent_id) if unit.parent_id else None,
            "archived": unit.archived,
            **row(unit.id),
        }
        for unit in units
    ]
    return {
        **payload,
        "state": "measured",
        "units": rows,
        "no_home_unit": row(None),
        "chart": _chart(rows),
    }
