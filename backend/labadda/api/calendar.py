"""Google-grade Central & Hierarchical Calendar API.

Supports site-wide events, hierarchical workspace events (upward-only inheritance),
flat private workspaces (projects/groups), and isolated personal calendars.
Strictly enforces administrator blindness for personal events.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import policy
from ..calendar_access import _can_manage_event, _can_manage_site, _event_out, _source_color, lock_calendar
from ..calendar_schemas import CalendarEventOut, CalendarSourceOut, EventCreate, EventUpdate
from ..deps import Actor, current_actor, get_db
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import CalendarEvent, User, Workspace
from ..security import utcnow

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/sources", response_model=list[CalendarSourceOut])
def get_sources(
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[CalendarSourceOut]:
    lock_calendar(request, actor, db)
    sources: list[CalendarSourceOut] = [
        CalendarSourceOut(
            id="personal",
            title="My Calendar",
            kind="personal",
            level=None,
            color=_source_color("personal"),
            can_write=True,
            inherited=False,
        ),
        CalendarSourceOut(
            id="site",
            title="Institute Events",
            kind="site",
            level="organisation",
            color=_source_color("site"),
            can_write=_can_manage_site(db, actor),
            inherited=False,
        ),
    ]

    readable_map = policy.readable_workspace_ids(db, actor.user)
    if not readable_map:
        return sources

    workspaces = db.scalars(
        select(Workspace).where(Workspace.id.in_(list(readable_map.keys()))).order_by(Workspace.name.asc())
    ).all()

    for ws in workspaces:
        direct_role = readable_map.get(ws.id)
        is_steward = direct_role == "steward"
        can_write = not ws.archived and (ws.posting_policy == "open" or is_steward)
        sources.append(
            CalendarSourceOut(
                id=str(ws.id),
                title=ws.name,
                kind=ws.kind,
                level=ws.level,
                color=_source_color(ws.kind, ws.level),
                can_write=can_write,
                inherited=direct_role is None,
            )
        )
    return sources


def _selected_workspaces(tokens: set[str] | None, readable_ids: set[uuid.UUID]) -> set[uuid.UUID]:
    if tokens is None:
        return readable_ids
    selected = set()
    for token in tokens:
        try:
            value = uuid.UUID(token.strip())
        except ValueError:
            continue
        if value in readable_ids:
            selected.add(value)
    return selected


@router.get("/events", response_model=list[CalendarEventOut])
def get_events(
    request: Request,
    *,
    start: datetime = Query(...),
    end: datetime = Query(...),
    sources: str | None = Query(default=None, max_length=10000),
    search: str | None = Query(default=None, max_length=200),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[CalendarEventOut]:
    lock_calendar(request, actor, db)
    if start.tzinfo is None or end.tzinfo is None or not start <= end <= start + timedelta(days=366):
        raise Invalid("invalid_calendar_range", "Choose a time zone and a range of at most 366 days.")
    readable_map = policy.readable_workspace_ids(db, actor.user)
    readable_ids = set(readable_map.keys())

    tokens = set(sources.split(",")) if sources else None
    include_personal = tokens is None or "personal" in tokens
    include_site = tokens is None or "site" in tokens

    selected_ws_ids = _selected_workspaces(tokens, readable_ids)

    scope_clauses = []
    if include_personal:
        scope_clauses.append(
            (CalendarEvent.scope_kind == "personal") & (CalendarEvent.owner_id == actor.user.id)
        )
    if include_site:
        scope_clauses.append(CalendarEvent.scope_kind == "site")
    if selected_ws_ids:
        scope_clauses.append(
            (CalendarEvent.scope_kind == "workspace") & (CalendarEvent.workspace_id.in_(selected_ws_ids))
        )

    if not scope_clauses:
        return []

    time_clause = (CalendarEvent.starts_at <= end) & (CalendarEvent.ends_at >= start)
    query = select(CalendarEvent).where(
        time_clause, CalendarEvent.cancelled_at.is_(None), or_(*scope_clauses)
    )

    if search and search.strip():
        escaped = search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        pat = f"%{escaped}%"
        query = query.where(
            or_(
                CalendarEvent.title.ilike(pat, escape="!"),
                CalendarEvent.description.ilike(pat, escape="!"),
                CalendarEvent.location.ilike(pat, escape="!"),
            )
        )

    events = db.scalars(query.order_by(CalendarEvent.starts_at.asc(), CalendarEvent.id).limit(1001)).all()
    if len(events) > 1000:
        raise Invalid("calendar_range_too_busy", "Choose a smaller date range or fewer calendars.")
    if not events:
        return []

    user_ids = {e.created_by for e in events}
    ws_ids = {e.workspace_id for e in events if e.workspace_id is not None}

    user_map = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    ws_map = {w.id: w.name for w in db.scalars(select(Workspace).where(Workspace.id.in_(ws_ids)))}

    result = []
    for ev in events:
        can_edit, can_del = _can_manage_event(db, actor, ev)
        result.append(
            CalendarEventOut(
                revision=ev.revision,
                id=ev.id,
                scope_kind=ev.scope_kind,
                workspace_id=ev.workspace_id,
                workspace_name=ws_map.get(ev.workspace_id) if ev.workspace_id else None,
                owner_id=ev.owner_id,
                created_by=ev.created_by,
                creator_name=user_map.get(ev.created_by),
                title=ev.title,
                description=ev.description,
                location=ev.location,
                starts_at=ev.starts_at,
                ends_at=ev.ends_at,
                all_day=ev.all_day,
                color=ev.color,
                created_at=ev.created_at,
                updated_at=ev.updated_at,
                can_edit=can_edit,
                can_delete=can_del,
            )
        )
    return result


@router.post("/events", response_model=CalendarEventOut)
def create_event(
    body: EventCreate,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    lock_calendar(request, actor, db)

    owner_id: uuid.UUID | None = None
    workspace_id: uuid.UUID | None = None

    if body.scope_kind == "personal":
        owner_id = actor.user.id
    elif body.scope_kind == "site":
        if not _can_manage_site(db, actor):
            raise Forbidden(
                "site_calendar_permission",
                "Only site administrators or root stewards can schedule site events.",
            )
    elif body.scope_kind == "workspace":
        if body.workspace_id is None:
            raise NotFound("workspace_not_found", "Workspace required.")
        access = policy.resolve(db, actor.user, body.workspace_id)
        if not access or not access.can_read:
            raise NotFound("workspace_not_found", "Workspace not found.")
        if not access.can_write:
            raise Forbidden("workspace_read_only", "You cannot schedule events in this workspace.")
        workspace_id = body.workspace_id

    event = CalendarEvent(
        id=uuid.uuid4(),
        scope_kind=body.scope_kind,
        workspace_id=workspace_id,
        owner_id=owner_id,
        created_by=actor.user.id,
        title=body.title.strip(),
        description=body.description.strip() if body.description else None,
        location=body.location.strip() if body.location else None,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        all_day=body.all_day,
        color=body.color,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    lock_calendar(request, actor, db)
    return _event_out(db, actor, event)


@router.get("/events/{event_id}", response_model=CalendarEventOut)
def get_event(
    event_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    lock_calendar(request, actor, db)
    event = db.scalar(select(CalendarEvent).where(CalendarEvent.id == event_id).with_for_update())
    if event is None or event.cancelled_at is not None:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "personal" and event.owner_id != actor.user.id:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            raise NotFound("event_not_found", "Event not found.")

    lock_calendar(request, actor, db)
    return _event_out(db, actor, event)


def _apply_event_updates(event: CalendarEvent, body: EventUpdate) -> None:
    if body.title is not None:
        event.title = body.title.strip()
    if body.description is not None:
        event.description = body.description.strip() if body.description else None
    if body.location is not None:
        event.location = body.location.strip() if body.location else None
    if body.starts_at is not None:
        event.starts_at = body.starts_at
    if body.ends_at is not None:
        event.ends_at = body.ends_at
    if body.all_day is not None:
        event.all_day = body.all_day
    if body.color is not None:
        event.color = body.color


@router.patch("/events/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    lock_calendar(request, actor, db)
    event = db.scalar(select(CalendarEvent).where(CalendarEvent.id == event_id).with_for_update())
    if event is None or event.cancelled_at is not None:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "personal" and event.owner_id != actor.user.id:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            raise NotFound("event_not_found", "Event not found.")

    can_edit, _can_del = _can_manage_event(db, actor, event)
    if not can_edit:
        raise Forbidden("edit_forbidden", "You cannot edit this event.")

    if event.revision != body.revision:
        raise Conflict("stale_revision", "This event changed. Reopen it and review the latest version.")
    new_starts = body.starts_at if body.starts_at is not None else event.starts_at
    new_ends = body.ends_at if body.ends_at is not None else event.ends_at
    if new_starts > new_ends:
        raise Forbidden("invalid_dates", "Start time must be before end time.")

    _apply_event_updates(event, body)

    event.revision += 1
    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)

    lock_calendar(request, actor, db)
    return _event_out(db, actor, event)


@router.delete("/events/{event_id}")
def delete_event(
    event_id: uuid.UUID,
    request: Request,
    revision: int = Query(ge=1),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    lock_calendar(request, actor, db)
    event = db.scalar(select(CalendarEvent).where(CalendarEvent.id == event_id).with_for_update())
    if event is None or event.cancelled_at is not None:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "personal" and event.owner_id != actor.user.id:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            raise NotFound("event_not_found", "Event not found.")

    _, can_del = _can_manage_event(db, actor, event)
    if not can_del:
        raise Forbidden("delete_forbidden", "You cannot delete this event.")

    if event.revision != revision:
        raise Conflict("stale_revision", "This event changed. Reopen it before cancelling.")
    event.cancelled_at = utcnow()
    event.updated_at = event.cancelled_at
    event.revision += 1
    db.commit()
    return {"ok": True}
