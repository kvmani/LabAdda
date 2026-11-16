"""Calendar access uses current identity and grant locks, including delivery."""

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import policy
from .api.todos import _scope_locks
from .calendar_schemas import CalendarEventOut
from .deps import Actor, get_settings
from .errors import Unauthenticated
from .identity_locks import lock_identity
from .models import CalendarEvent, User, Workspace

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


def _can_manage_event(db: Session, actor: Actor, event: CalendarEvent) -> tuple[bool, bool]:
    if event.scope_kind == "personal":
        is_owner = event.owner_id == actor.user.id
        return (is_owner, is_owner)
    if event.scope_kind == "site":
        allowed = _can_manage_site(db, actor)
        return (allowed, allowed)
    if event.scope_kind == "workspace" and event.workspace_id is not None:
        access = policy.resolve(db, actor.user, event.workspace_id)
        if not access or not access.can_read or not access.can_write:
            return (False, False)
        is_creator = event.created_by == actor.user.id and access.can_write
        is_steward_or_admin = access.can_moderate or actor.user.is_admin
        can_manage = is_creator or is_steward_or_admin
        return (can_manage, can_manage)
    return (False, False)


def lock_calendar(request: Request, actor: Actor, db: Session) -> None:
    if request.headers.get("x-labadda-panel") or request.query_params.get("panel") == "1":
        raise Unauthenticated("session_scope", "Touch panels cannot access calendar.")
    actor.user = lock_identity(db, actor, get_settings(request))
    # Shared locks fence grant changes through response serialization.
    _scope_locks(db, None)


def _event_out(db: Session, actor: Actor, event: CalendarEvent) -> CalendarEventOut:
    creator = db.get(User, event.created_by)
    workspace = db.get(Workspace, event.workspace_id) if event.workspace_id else None
    can_edit, can_delete = _can_manage_event(db, actor, event)
    return CalendarEventOut(
        **{
            name: getattr(event, name)
            for name in CalendarEventOut.model_fields
            if name not in {"workspace_name", "creator_name", "can_edit", "can_delete"}
        },
        workspace_name=workspace.name if workspace else None,
        creator_name=creator.display_name if creator else None,
        can_edit=can_edit,
        can_delete=can_delete,
    )
