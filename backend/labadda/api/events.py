"""Operational events: list with filters and cursor paging, acknowledge, resolve (AD-06, AD-12)."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import audit
from ..deps import Actor, get_db, require_console
from ..errors import ApiError, Conflict, Invalid, NotFound
from ..health import BY_KEY
from ..health.types import PROBLEMS
from ..models import OpsEvent, User
from ..security import utcnow
from ..serialize import iso, user_brief

router = APIRouter(prefix="/admin/events", tags=["events"])
console_events = require_console("events")
console_events_write = require_console("events", admin_only=True)

UNAVAILABLE = ("events_unavailable", "Events are unavailable. Try again.")
PAGE_SIZE = 25
MAX_PAGE = 100
Severity = Literal["info", "warning", "error", "critical"]
State = Literal["open", "acknowledged", "resolved"]


class Acknowledge(BaseModel):
    note: str = Field(max_length=500)

    @field_validator("note")
    @classmethod
    def _needs_words(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write a short note saying what you know or will do.")
        return value


class Resolve(BaseModel):
    note: str = Field(default="", max_length=500)


def _encode(event: OpsEvent) -> str:
    raw = json.dumps([event.last_at.isoformat(), event.id]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, int]:
    try:
        last_at, event_id = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(last_at), int(event_id)
    except (ValueError, TypeError, binascii.Error):
        raise Invalid("invalid_cursor", "That page of events is no longer available.") from None


def event_json(event: OpsEvent, people: dict) -> dict:
    item = BY_KEY.get(event.component)
    return {
        "id": event.id,
        "code": event.code,
        "component": event.component,
        "component_label": item.label if item else event.component,
        "severity": event.severity,
        "summary": event.summary,
        "detail": event.detail,
        "first_at": iso(event.first_at),
        "last_at": iso(event.last_at),
        "count": event.count,
        "state": event.state,
        "acknowledged_by": user_brief(people.get(event.acknowledged_by)),
        "acknowledged_at": iso(event.acknowledged_at),
        "note": event.note,
        "resolved_at": iso(event.resolved_at),
        "help": f"troubleshooting/{item.help}" if item else None,
    }


def _people(db: Session, events: list[OpsEvent]) -> dict:
    ids = {event.acknowledged_by for event in events if event.acknowledged_by}
    if not ids:
        return {}
    return {user.id: user for user in db.scalars(select(User).where(User.id.in_(ids)))}


@router.get("")
def list_events(
    state: State | None = None,
    severity: Severity | None = None,
    component: str | None = Query(default=None, max_length=32),
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=PAGE_SIZE, ge=1, le=MAX_PAGE),
    *,
    actor: Actor = Depends(console_events),
    db: Session = Depends(get_db),
) -> dict:
    """Newest activity first; a stable order so paging survives new events arriving."""
    query = select(OpsEvent).order_by(OpsEvent.last_at.desc(), OpsEvent.id.desc()).limit(limit + 1)
    for column, value in (
        (OpsEvent.state, state),
        (OpsEvent.severity, severity),
        (OpsEvent.component, component),
    ):
        if value:
            query = query.where(column == value)
    if cursor:
        last_at, event_id = _decode(cursor)
        query = query.where(
            or_(OpsEvent.last_at < last_at, and_(OpsEvent.last_at == last_at, OpsEvent.id < event_id))
        )
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        found = db.scalars(query).all()
        people = _people(db, found)
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None
    page = found[:limit]
    return {
        "events": [event_json(event, people) for event in page],
        "next_cursor": _encode(page[-1]) if len(found) > limit else None,
    }


def _locked(db: Session, event_id: int) -> OpsEvent:
    event = db.scalar(select(OpsEvent).where(OpsEvent.id == event_id).with_for_update())
    if event is None:
        raise NotFound()
    return event


@router.post("/{event_id}/acknowledge")
def acknowledge(
    event_id: int,
    body: Acknowledge,
    actor: Actor = Depends(console_events_write),
    db: Session = Depends(get_db),
) -> dict:
    """Record that a person has seen the problem. The item's own state is never touched."""
    event = _locked(db, event_id)
    if event.state != "open":
        raise Conflict(f"event_{event.state}", "This event has already been dealt with.")
    event.state = "acknowledged"
    event.acknowledged_by = actor.user.id
    event.acknowledged_at = utcnow()
    event.note = body.note
    audit.record(
        db,
        actor=actor.user,
        action="ops_event.acknowledge",
        scope_type="site",
        target_id=event.id,
        reason=body.note,
        code=event.code,
        before="open",
        after="acknowledged",
    )
    db.commit()
    return event_json(event, {actor.user.id: actor.user})


@router.post("/{event_id}/resolve")
def resolve(
    event_id: int,
    request: Request,
    body: Resolve | None = None,
    actor: Actor = Depends(console_events_write),
    db: Session = Depends(get_db),
) -> dict:
    """Close an event by hand. An event whose check still fails resolves only when the check passes."""
    event = _locked(db, event_id)
    if event.state == "resolved":
        raise Conflict("event_resolved", "This event is already resolved.")
    current = request.app.state.health.current_status(event.component)
    if current in PROBLEMS:
        raise Conflict(
            "still_failing", "This problem is still present. It resolves itself once the check passes."
        )
    before = event.state
    event.state = "resolved"
    event.resolved_at = utcnow()
    audit.record(
        db,
        actor=actor.user,
        action="ops_event.resolve",
        scope_type="site",
        target_id=event.id,
        reason=(body.note.strip() if body else "") or None,
        code=event.code,
        before=before,
        after="resolved",
    )
    db.commit()
    return event_json(event, _people(db, [event]))
