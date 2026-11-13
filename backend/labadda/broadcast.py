"""Site broadcasts (AD-11): short announcements administrators show to every signed-in person.

A broadcast is site configuration written by an administrator, not user content, so unlike posts,
notes and files it may be deleted when it no longer matters. Every change is audited in the same
transaction, without the text (its length and the id are enough to tell which one changed).
"""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .errors import Conflict, Invalid, NotFound
from .models import SiteBroadcast, User
from .security import utcnow
from .serialize import iso

MAX_LENGTH = 300
MAX_BROADCASTS = 20
Level = Literal["info", "warning"]
PILOT_MESSAGE = (
    "The software is under pilot testing. Exercise caution in usage! Don't put any sensitive information."
)


def clean_message(text: str) -> str:
    """Plain text on one line: markup is shown as typed (the page escapes it), controls refused."""
    message = " ".join(text.split())
    if not message:
        raise Invalid("invalid_broadcast", "Write the message to show.")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in message):
        raise Invalid("invalid_broadcast", "The message may contain letters, numbers and punctuation only.")
    if len(message) > MAX_LENGTH:
        raise Invalid("broadcast_too_long", f"The message may be at most {MAX_LENGTH} characters.")
    return message


def status_of(row: SiteBroadcast, now: datetime) -> str:
    """Why a broadcast is or is not on screen: showing, scheduled, ended or off."""
    if not row.active:
        return "off"
    if row.starts_at is not None and row.starts_at > now:
        return "scheduled"
    if row.ends_at is not None and row.ends_at <= now:
        return "ended"
    return "showing"


def broadcast_json(row: SiteBroadcast, now: datetime) -> dict:
    return {
        "id": row.id,
        "message": row.message,
        "level": row.level,
        "starts_at": iso(row.starts_at),
        "ends_at": iso(row.ends_at),
        "active": row.active,
        "position": row.position,
        "status": status_of(row, now),
        "revision": row.revision,
    }


def list_all(db: Session, now: datetime | None = None) -> list[dict]:
    now = now or utcnow()
    rows = db.scalars(select(SiteBroadcast).order_by(SiteBroadcast.position, SiteBroadcast.id))
    return [broadcast_json(row, now) for row in rows]


def showing_now(db: Session, now: datetime | None = None) -> list[dict]:
    """What every signed-in person sees: only broadcasts on screen now, in order, with no admin fields."""
    now = now or utcnow()
    rows = db.scalars(select(SiteBroadcast).order_by(SiteBroadcast.position, SiteBroadcast.id))
    return [
        {"id": row.id, "message": row.message, "level": row.level}
        for row in rows
        if status_of(row, now) == "showing"
    ]


def _check_window(starts_at: datetime | None, ends_at: datetime | None, now: datetime) -> None:
    if ends_at is not None and (ends_at <= now or (starts_at is not None and ends_at <= starts_at)):
        raise Invalid("invalid_broadcast_times", "The message must end after it starts, and in the future.")


def _facts(row: SiteBroadcast) -> dict:
    return {
        "level": row.level,
        "starts_at": iso(row.starts_at),
        "ends_at": iso(row.ends_at),
        "active": row.active,
    }


def add(
    db: Session,
    actor: User | None,
    *,
    message: str,
    level: Level,
    starts_at: datetime | None,
    ends_at: datetime | None,
    active: bool = True,
    seeded: bool = False,
    reason: str | None = None,
) -> SiteBroadcast:
    now = utcnow()
    text = clean_message(message)
    _check_window(starts_at, ends_at, now)
    db.execute(select(func.pg_advisory_xact_lock(39_001)))
    if db.scalar(select(func.count()).select_from(SiteBroadcast)) >= MAX_BROADCASTS:
        raise Conflict(
            "too_many_broadcasts", f"At most {MAX_BROADCASTS} broadcasts can be kept. Delete one first."
        )
    last = db.scalar(select(func.max(SiteBroadcast.position))) or 0
    row = SiteBroadcast(
        message=text,
        level=level,
        starts_at=starts_at,
        ends_at=ends_at,
        active=active,
        position=last + 1,
        revision=1,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="site.broadcast_seed" if seeded else "site.broadcast_add",
        scope_type="site",
        target_id=row.id,
        reason=reason,
        after=_facts(row),
        message_length=len(text),
    )
    db.commit()
    return row


def _locked(db: Session, broadcast_id: int) -> SiteBroadcast:
    row = db.get(SiteBroadcast, broadcast_id, with_for_update=True)
    if row is None:
        raise NotFound()
    return row


def edit(
    db: Session, actor: User, broadcast_id: int, *, changes: dict, expected_revision: int
) -> SiteBroadcast:
    """Apply only the fields present in `changes`; a stale revision is refused, not overwritten."""
    row = _locked(db, broadcast_id)
    if row.revision != expected_revision:
        raise Conflict(
            "broadcast_changed", "This broadcast was changed by someone else. Reload and try again."
        )
    now = utcnow()
    before = _facts(row)
    if "message" in changes:
        row.message = clean_message(changes["message"])
    for name in ("level", "starts_at", "ends_at", "active"):
        if name in changes:
            setattr(row, name, changes[name])
    if "ends_at" in changes and row.ends_at is not None and row.ends_at <= now:
        raise Invalid("invalid_broadcast_times", "The message must end in the future.")
    if row.starts_at is not None and row.ends_at is not None and row.ends_at <= row.starts_at:
        raise Invalid("invalid_broadcast_times", "The message must end after it starts.")
    row.revision += 1
    row.updated_at = now
    audit.record(
        db,
        actor=actor,
        action="site.broadcast_edit",
        scope_type="site",
        target_id=row.id,
        before=before,
        after=_facts(row),
        message_length=len(row.message),
    )
    db.commit()
    return row


def move(db: Session, actor: User, broadcast_id: int, direction: Literal["up", "down"]) -> None:
    """Swap with the neighbour so the order people read in is the order administrators set."""
    db.execute(select(func.pg_advisory_xact_lock(39_001)))
    rows = list(db.scalars(select(SiteBroadcast).order_by(SiteBroadcast.position, SiteBroadcast.id)))
    index = next((i for i, row in enumerate(rows) if row.id == broadcast_id), None)
    if index is None:
        raise NotFound()
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(rows):
        rows[index], rows[other] = rows[other], rows[index]
        now = utcnow()
        for number, row in enumerate(rows, start=1):
            if row.position != number:
                row.position, row.updated_at = number, now
                row.revision += 1
        audit.record(
            db,
            actor=actor,
            action="site.broadcast_move",
            scope_type="site",
            target_id=broadcast_id,
            direction=direction,
        )
    db.commit()


def delete(db: Session, actor: User, broadcast_id: int) -> None:
    row = _locked(db, broadcast_id)
    audit.record(
        db,
        actor=actor,
        action="site.broadcast_delete",
        scope_type="site",
        target_id=row.id,
        before=_facts(row),
        message_length=len(row.message),
    )
    db.delete(row)
    db.commit()


def seed_pilot_notice(db: Session) -> None:
    """First run of a pilot install: show the pilot-testing warning until an administrator removes it."""
    add(
        db,
        None,
        message=PILOT_MESSAGE,
        level="warning",
        starts_at=None,
        ends_at=None,
        seeded=True,
        reason="First-run setup of a pilot installation",
    )
