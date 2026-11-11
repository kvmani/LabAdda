"""User-created collaborative groups (S2.1).

A collaborative group is a flat workspace (``kind = 'group'``) with the same
noticeboard, whiteboard, chat, search and reminder features as a section or
division. It has no parent, no descendants and no inherited access: only
direct members can read it. Its creator becomes its first steward. Stewards
manage membership; any member may leave. The last active steward cannot
leave or step down until another member is made a steward.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import audit, memberships, policy
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Forbidden, Invalid, NotFound
from ..models import Membership, User, Workspace
from ..serialize import user_brief, workspace_json

router = APIRouter(tags=["groups"])


def _hub(request: Request):
    return request.app.state.hub


class NewGroup(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


class GroupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    archived: bool | None = None


class AddMembers(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    role: str = "member"


class RoleBody(BaseModel):
    role: str


def _group_access(db: Session, actor: Actor, group_id: uuid.UUID, *, steward: bool):
    access = policy.require_read(db, actor.user, group_id)
    if access.workspace.kind != "group":
        raise NotFound()
    if steward and not access.can_moderate:
        raise Forbidden("steward_required", "Only a steward of this group can do that.")
    return access


def _active_users(db: Session, ids: list[uuid.UUID]) -> list[User]:
    if not ids:
        return []
    users = db.scalars(select(User).where(User.id.in_(set(ids)), User.is_active.is_(True))).all()
    if len(users) != len(set(ids)):
        raise Invalid("unknown_member", "One or more chosen colleagues are not active accounts.")
    return list(users)


def _member_count(db: Session, group_id: uuid.UUID) -> int:
    return (
        db.scalar(select(func.count()).select_from(Membership).where(Membership.workspace_id == group_id))
        or 0
    )


@router.get("/directory")
def directory(
    q: str = Query(default="", max_length=64),
    limit: int = Query(default=20, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    """Find active colleagues to invite. Returns names only, never memberships."""
    stmt = select(User).where(User.is_active.is_(True))
    term = q.strip().lower()
    if term:
        like = f"%{term.replace('%', '').replace('_', '')}%"
        stmt = stmt.where(or_(User.username.ilike(like), func.lower(User.display_name).like(like)))
    users = db.scalars(stmt.order_by(User.display_name).limit(limit)).all()
    return {"users": [user_brief(u) for u in users if u.id != actor.id]}


@router.post("/groups", status_code=201)
def create_group(
    body: NewGroup,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    owned = (
        db.scalar(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.kind == "group", Workspace.created_by == actor.id, Workspace.archived.is_(False))
        )
        or 0
    )
    if owned >= settings.max_groups_per_user:
        raise Conflict(
            "group_limit",
            f"You can keep up to {settings.max_groups_per_user} active groups. "
            "Archive one before creating another.",
        )
    invitees = [u for u in _active_users(db, body.member_ids) if u.id != actor.id]
    if len(invitees) + 1 > settings.max_group_members:
        raise Invalid("group_too_large", f"A group can have up to {settings.max_group_members} members.")
    ws = Workspace(
        kind="group", name=body.name.strip(), description=body.description.strip(), created_by=actor.id
    )
    db.add(ws)
    db.flush()
    audit.record(db, actor=actor.user, action="group.create", scope_type="workspace", scope_id=ws.id)
    memberships.set_membership(db, actor=actor.user, workspace_id=ws.id, user_id=actor.id, role="steward")
    for u in invitees:
        memberships.set_membership(db, actor=actor.user, workspace_id=ws.id, user_id=u.id, role="member")
    db.commit()
    for u in invitees:
        _hub(request).revalidate_user(u.id)
    return workspace_json(ws, policy.resolve(db, actor.user, ws.id))


@router.patch("/groups/{group_id}")
def update_group(
    group_id: uuid.UUID,
    body: GroupPatch,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    _group_access(db, actor, group_id, steward=True)
    ws = db.get(Workspace, group_id, with_for_update=True)
    if ws.archived and body.archived is not False and (body.name or body.description is not None):
        raise Forbidden("workspace_archived", "Unarchive the group before editing it.")
    if body.name is not None:
        ws.name = body.name.strip()
    if body.description is not None:
        ws.description = body.description.strip()
    if body.archived is not None and body.archived != ws.archived:
        ws.archived = body.archived
        audit.record(
            db,
            actor=actor.user,
            action="group.archive" if body.archived else "group.unarchive",
            scope_type="workspace",
            scope_id=ws.id,
        )
    db.commit()
    _hub(request).revalidate_workspace(ws.id)
    return workspace_json(ws, policy.resolve(db, actor.user, ws.id))


@router.post("/groups/{group_id}/members")
def add_members(
    group_id: uuid.UUID,
    body: AddMembers,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    access = _group_access(db, actor, group_id, steward=True)
    if access.workspace.archived:
        raise Forbidden("workspace_archived", "Unarchive the group before adding members.")
    if body.role not in ("member", "steward"):
        raise Invalid("invalid_role", "Role must be member or steward.")
    users = _active_users(db, body.user_ids)
    existing = set(policy.direct_grants_for_workspace(db, group_id))
    new = [u for u in users if u.id not in existing]
    if _member_count(db, group_id) + len(new) > settings.max_group_members:
        raise Invalid("group_too_large", f"A group can have up to {settings.max_group_members} members.")
    for u in new:
        memberships.set_membership(db, actor=actor.user, workspace_id=group_id, user_id=u.id, role=body.role)
    db.commit()
    for u in new:
        _hub(request).revalidate_user(u.id)
    return {"added": [user_brief(u) for u in new]}


@router.patch("/groups/{group_id}/members/{user_id}")
def change_role(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    body: RoleBody,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    access = _group_access(db, actor, group_id, steward=True)
    if access.workspace.archived:
        raise Forbidden("workspace_archived", "Unarchive the group before changing roles.")
    if body.role not in ("member", "steward"):
        raise Invalid("invalid_role", "Role must be member or steward.")
    if user_id not in policy.direct_grants_for_workspace(db, group_id):
        raise NotFound()
    memberships.set_membership(
        db,
        actor=actor.user,
        workspace_id=group_id,
        user_id=user_id,
        role=body.role,
        protect_last_steward=True,
    )
    db.commit()
    _hub(request).revalidate_user(user_id)
    return {"ok": True}


@router.delete("/groups/{group_id}/members/{user_id}")
def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    leaving = user_id == actor.id
    _group_access(db, actor, group_id, steward=not leaving)
    if not memberships.remove_membership(
        db,
        actor=actor.user,
        workspace_id=group_id,
        user_id=user_id,
        protect_last_steward=True,
        reason="left" if leaving else None,
    ):
        raise NotFound()
    db.commit()
    _hub(request).revalidate_user(user_id)
    return {"ok": True}
