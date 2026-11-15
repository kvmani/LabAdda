"""Google-grade Central & Hierarchical Calendar API.

Supports site-wide events, hierarchical workspace events (upward-only inheritance),
flat private workspaces (projects/groups), and isolated personal calendars.
Strictly enforces administrator blindness for personal events.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Self

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import policy
from ..deps import Actor, current_actor, get_db
from ..errors import Forbidden, NotFound, Unauthenticated
from ..models import CalendarEvent, User, Workspace
from ..security import utcnow

router = APIRouter(prefix="/calendar", tags=["calendar"])


class EventCreate(BaseModel):
    scope_kind: Literal["site", "workspace", "personal"]
    workspace_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=140)
    description: str | None = None
    location: str | None = Field(default=None, max_length=140)
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    color: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def check_dates_and_scope(self) -> Self:
        if self.starts_at > self.ends_at:
            raise ValueError("starts_at must be before or equal to ends_at")
        if self.scope_kind == "personal" and self.workspace_id is not None:
            raise ValueError("personal events cannot have a workspace_id")
        if self.scope_kind == "workspace" and self.workspace_id is None:
            raise ValueError("workspace events must have a workspace_id")
        if self.scope_kind == "site" and self.workspace_id is not None:
            raise ValueError("site events cannot have a workspace_id")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = None
    location: str | None = Field(default=None, max_length=140)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    color: str | None = Field(default=None, max_length=32)


class CalendarSourceOut(BaseModel):
    id: str
    title: str
    kind: str
    level: str | None = None
    color: str
    can_write: bool
    inherited: bool = False


class CalendarEventOut(BaseModel):
    id: uuid.UUID
    scope_kind: str
    workspace_id: uuid.UUID | None
    workspace_name: str | None
    owner_id: uuid.UUID | None
    created_by: uuid.UUID
    creator_name: str | None
    title: str
    description: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    color: str | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool


COLOR_MAP: dict[tuple[str, str], str] = {
    ("kind", "personal"): "#d81b60",
    ("kind", "site"): "#1565c0",
    ("kind", "project"): "#ef6c00",
    ("kind", "group"): "#2e7d32",
    ("level", "organisation"): "#1565c0",
    ("level", "division"): "#6a1b9a",
    ("level", "section"): "#00838f",
    ("level", "group"): "#2e7d32",
}


def _source_color(kind: str, level: str | None = None) -> str:
    if level and ("level", level) in COLOR_MAP:
        return COLOR_MAP[("level", level)]
    return COLOR_MAP.get(("kind", kind), "#3f51b5")


def _can_manage_site(db: Session, actor: Actor) -> bool:
    if actor.user.is_admin:
        return True
    root_ws = db.scalars(
        select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None))
    ).first()
    if root_ws is None:
        return False
    grants = policy.direct_grants(db, actor.user.id)
    return grants.get(root_ws.id) == "steward"


def _can_manage_event(
    db: Session, actor: Actor, event: CalendarEvent
) -> tuple[bool, bool]:
    if event.scope_kind == "personal":
        is_owner = event.owner_id == actor.user.id
        return (is_owner, is_owner)
    if event.scope_kind == "site":
        allowed = _can_manage_site(db, actor)
        return (allowed, allowed)
    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            return (False, False)
        is_creator = event.created_by == actor.user.id and access.can_write
        is_steward_or_admin = access.can_moderate or actor.user.is_admin
        can_manage = is_creator or is_steward_or_admin
        return (can_manage, can_manage)
    return (False, False)


def _check_panel(request: Request) -> None:
    if request.headers.get("x-labadda-panel"):
        raise Unauthenticated("session_scope", "Touch panels cannot access calendar.")


@router.get("/sources", response_model=list[CalendarSourceOut])
def get_sources(
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[CalendarSourceOut]:
    _check_panel(request)
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
        select(Workspace)
        .where(Workspace.id.in_(list(readable_map.keys())))
        .order_by(Workspace.name.asc())
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


@router.get("/events", response_model=list[CalendarEventOut])
def get_events(
    request: Request,
    *,
    start: datetime = Query(...),
    end: datetime = Query(...),
    sources: str | None = Query(default=None),
    search: str | None = Query(default=None),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> list[CalendarEventOut]:
    _check_panel(request)
    readable_map = policy.readable_workspace_ids(db, actor.user)
    readable_ids = set(readable_map.keys())

    tokens = set(sources.split(",")) if sources else None
    include_personal = tokens is None or "personal" in tokens
    include_site = tokens is None or "site" in tokens

    selected_ws_ids: set[uuid.UUID] = set()
    if tokens is None:
        selected_ws_ids = readable_ids
    else:
        for t in tokens:
            try:
                u = uuid.UUID(t.strip())
                if u in readable_ids:
                    selected_ws_ids.add(u)
            except ValueError:
                continue

    scope_clauses = []
    if include_personal:
        scope_clauses.append(
            (CalendarEvent.scope_kind == "personal")
            & (CalendarEvent.owner_id == actor.user.id)
        )
    if include_site:
        scope_clauses.append(CalendarEvent.scope_kind == "site")
    if selected_ws_ids:
        scope_clauses.append(
            (CalendarEvent.scope_kind == "workspace")
            & (CalendarEvent.workspace_id.in_(selected_ws_ids))
        )

    if not scope_clauses:
        return []

    time_clause = (CalendarEvent.starts_at <= end) & (CalendarEvent.ends_at >= start)
    query = select(CalendarEvent).where(time_clause, or_(*scope_clauses))

    if search and search.strip():
        pat = f"%{search.strip()}%"
        query = query.where(
            or_(
                CalendarEvent.title.ilike(pat),
                CalendarEvent.description.ilike(pat),
                CalendarEvent.location.ilike(pat),
            )
        )

    events = db.scalars(query.order_by(CalendarEvent.starts_at.asc())).all()
    if not events:
        return []

    user_ids = {e.created_by for e in events}
    ws_ids = {e.workspace_id for e in events if e.workspace_id is not None}

    user_map = {
        u.id: u.display_name
        for u in db.scalars(select(User).where(User.id.in_(user_ids)))
    }
    ws_map = {
        w.id: w.name
        for w in db.scalars(select(Workspace).where(Workspace.id.in_(ws_ids)))
    }

    result = []
    for ev in events:
        can_edit, can_del = _can_manage_event(db, actor, ev)
        result.append(
            CalendarEventOut(
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
    _check_panel(request)

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

    ws_name = None
    if workspace_id:
        ws = db.get(Workspace, workspace_id)
        ws_name = ws.name if ws else None

    return CalendarEventOut(
        id=event.id,
        scope_kind=event.scope_kind,
        workspace_id=event.workspace_id,
        workspace_name=ws_name,
        owner_id=event.owner_id,
        created_by=event.created_by,
        creator_name=actor.user.display_name,
        title=event.title,
        description=event.description,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        all_day=event.all_day,
        color=event.color,
        created_at=event.created_at,
        updated_at=event.updated_at,
        can_edit=True,
        can_delete=True,
    )


@router.get("/events/{event_id}", response_model=CalendarEventOut)
def get_event(
    event_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> CalendarEventOut:
    _check_panel(request)
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "personal" and event.owner_id != actor.user.id:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            raise NotFound("event_not_found", "Event not found.")

    can_edit, can_del = _can_manage_event(db, actor, event)
    creator = db.get(User, event.created_by)
    ws = db.get(Workspace, event.workspace_id) if event.workspace_id else None

    return CalendarEventOut(
        id=event.id,
        scope_kind=event.scope_kind,
        workspace_id=event.workspace_id,
        workspace_name=ws.name if ws else None,
        owner_id=event.owner_id,
        created_by=event.created_by,
        creator_name=creator.display_name if creator else None,
        title=event.title,
        description=event.description,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        all_day=event.all_day,
        color=event.color,
        created_at=event.created_at,
        updated_at=event.updated_at,
        can_edit=can_edit,
        can_delete=can_del,
    )


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
    _check_panel(request)
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "personal" and event.owner_id != actor.user.id:
        raise NotFound("event_not_found", "Event not found.")

    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read:
            raise NotFound("event_not_found", "Event not found.")

    can_edit, can_del = _can_manage_event(db, actor, event)
    if not can_edit:
        raise Forbidden("edit_forbidden", "You cannot edit this event.")

    new_starts = body.starts_at if body.starts_at is not None else event.starts_at
    new_ends = body.ends_at if body.ends_at is not None else event.ends_at
    if new_starts > new_ends:
        raise Forbidden("invalid_dates", "Start time must be before end time.")

    _apply_event_updates(event, body)

    event.updated_at = utcnow()
    db.commit()
    db.refresh(event)

    creator = db.get(User, event.created_by)
    ws = db.get(Workspace, event.workspace_id) if event.workspace_id else None

    return CalendarEventOut(
        id=event.id,
        scope_kind=event.scope_kind,
        workspace_id=event.workspace_id,
        workspace_name=ws.name if ws else None,
        owner_id=event.owner_id,
        created_by=event.created_by,
        creator_name=creator.display_name if creator else None,
        title=event.title,
        description=event.description,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        all_day=event.all_day,
        color=event.color,
        created_at=event.created_at,
        updated_at=event.updated_at,
        can_edit=can_edit,
        can_delete=can_del,
    )


@router.delete("/events/{event_id}")
def delete_event(
    event_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _check_panel(request)
    event = db.get(CalendarEvent, event_id)
    if event is None:
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

    db.delete(event)
    db.commit()
    return {"ok": True}
