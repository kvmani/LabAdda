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


def _items_by_unit(db: Session, window: Window) -> dict[str, float]:
    found: dict[str, float] = {}
    for (_, dimension), value in samples.totals(db, ITEM_METRICS, window).items():
        if dimension.startswith(catalog.UNIT_PREFIX) and dimension != catalog.UNIT_OVERFLOW:
            found[dimension] = found.get(dimension, 0.0) + value
    return found


def _unit_items(items: dict[str, float] | None, key: uuid.UUID | None, visible: bool) -> dict | None:
    """Items made in a unit's own space; people without a home unit have no space."""
    if key is None:
        return None
    if visible and items is None:
        return {"state": "unknown"}
    return protect.figure((items or {}).get(catalog.unit_dimension(key), 0.0), visible, people=False)


def _figures(
    db: Session, window: Window, keys: list[uuid.UUID | None], headcount: dict
) -> dict[uuid.UUID | None, dict]:
    """Each row's published figures for one window; suppression is decided on exact values."""
    active = samples.active_by_home_unit(db, window)
    items = _items_by_unit(db, window) if samples.has_samples(db, window) else None
    at_risk = {key: active.get(key, 0) for key in keys if headcount.get(key, 0) > 0}
    shown = protect.published(at_risk)
    figures = {}
    for key in keys:
        visible = key in shown
        figures[key] = {
            "active_people": protect.figure(active.get(key, 0), visible, people=True),
            "items_created": _unit_items(items, key, visible),
        }
    return figures


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
