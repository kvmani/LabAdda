"""The attention list: what is not healthy, what is open, and which units have nobody in charge.

Every entry names the console page that fixes it. Entries hold statuses, counts, unit names and the
sanitised summaries the health and event tables already keep; never user content (AD-02).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..health import BY_KEY
from ..models import OpsEvent
from ..serialize import iso
from . import people_attention

SEVERITIES = ("critical", "error", "warning", "info")
KIND_ORDER = {"health": 0, "event": 1, "people": 2}
HEALTH_SEVERITY = {"unavailable": "error", "degraded": "warning", "stale": "warning", "unknown": "info"}
# More open events than this are folded into one entry so a storm cannot bury everything else.
MAX_EVENT_ENTRIES = 10


def health_entries(items: list[dict]) -> list[dict]:
    """One entry per item that is not healthy; "unsupported" is not a problem (AD-03)."""
    entries = []
    for item in items:
        word = item["status"]
        if word in ("healthy", "unsupported"):
            continue
        entries.append(
            {
                "id": f"health:{item['key']}",
                "kind": "health",
                "severity": HEALTH_SEVERITY[word],
                "status": word,
                "title": item["label"],
                "detail": item["detail"],
                "route": "/admin/backups" if item["key"] == "backups" else "/admin/health",
                "help": item["help"],
                "at": item["checked_at"],
            }
        )
    return entries


def open_events(db: Session) -> list[OpsEvent]:
    """Events nobody has acknowledged yet, worst first, newest first within a severity."""
    return list(
        db.scalars(select(OpsEvent).where(OpsEvent.state == "open").order_by(OpsEvent.last_at.desc()))
    )


def event_entries(events: list[OpsEvent], covered: set[str]) -> list[dict]:
    """Open events, except those about an item already listed (its health entry says the same)."""
    shown = [event for event in events if event.component not in covered]
    ranked = sorted(shown, key=lambda event: SEVERITIES.index(event.severity))
    entries = []
    for event in ranked[:MAX_EVENT_ENTRIES]:
        item = BY_KEY.get(event.component)
        entries.append(
            {
                "id": f"event:{event.id}",
                "kind": "event",
                "severity": event.severity,
                "status": None,
                "title": event.summary,
                "detail": f"{item.label if item else event.component}, seen {event.count} "
                + ("time." if event.count == 1 else "times."),
                "route": f"/admin/events?state=open&event={event.id}",
                "help": f"troubleshooting/{item.help}" if item else None,
                "at": iso(event.last_at),
            }
        )
    rest = ranked[MAX_EVENT_ENTRIES:]
    if rest:
        entries.append(
            {
                "id": "event:more",
                "kind": "event",
                "severity": SEVERITIES[min(SEVERITIES.index(event.severity) for event in rest)],
                "status": None,
                "title": f"{len(rest)} more open events",
                "detail": "Open the events page to read them all.",
                "route": "/admin/events?state=open",
                "help": None,
                "at": iso(max(event.last_at for event in rest)),
            }
        )
    return entries


def people_entries(db: Session, settings: Settings, now: datetime) -> list[dict]:
    """PO-22 items, kept in ``people_attention`` so this module stays about health and events."""
    return people_attention.people_entries(db, settings, now)


def ordered(entries: list[dict]) -> list[dict]:
    """Most severe first, then health, events, people; stable within each group."""
    return sorted(entries, key=lambda entry: (SEVERITIES.index(entry["severity"]), KIND_ORDER[entry["kind"]]))
