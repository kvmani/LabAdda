"""Identity and hierarchy administration (S2). Administrators get no content access here."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from .. import audit, memberships, people, policy
from ..config import Settings
from ..credentials import issue_credential
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import Conflict, Invalid, NotFound
from ..models import Membership, User, Workspace
from ..people import USERNAME_RE
from ..security import revoke_user_sessions, utcnow
from ..serialize import iso, user_brief, workspace_json

router = APIRouter(prefix="/admin", tags=["admin"])
console_people = require_console("people")
console_org = require_console("org")


def _hub(request: Request):
    return request.app.state.hub


class NewUser(BaseModel):
    username: str = Field(max_length=64)
    display_name: str = Field(min_length=1, max_length=120)
    is_admin: bool = False


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    is_admin: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


def _admin_user_json(u: User) -> dict:
    return {
        **user_brief(u),
        "is_admin": u.is_admin,
        "must_set_password": u.must_set_password,
        "created_at": iso(u.created_at),
        "deactivated_at": iso(u.deactivated_at),
    }


@router.get("/users")
def list_users(_: Actor = Depends(console_people), db: Session = Depends(get_db)):
    return {"users": [_admin_user_json(u) for u in db.scalars(select(User).order_by(User.username))]}


@router.post("/users", status_code=201)
def create_user(
    body: NewUser,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    username = body.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise Invalid("invalid_username", "Use 2-63 lowercase letters, digits, dot, dash or underscore.")
    if db.scalar(select(User).where(User.username == username)):
        raise Conflict("username_taken", "That username is already in use.")
    user = User(
        username=username,
        display_name=body.display_name.strip(),
        is_admin=body.is_admin,
        must_set_password=True,
    )
    people.set_status(user, "invited", effective_on=people.site_date(settings))
    db.add(user)
    db.flush()
    token, cred = issue_credential(db, user, "activation", actor.user, settings)
    audit.record(
        db,
        actor=actor.user,
        action="identity.create",
        scope_type="identity",
        target_id=user.id,
        is_admin=body.is_admin,
        status_before=None,
        status_after=user.status,
    )
    db.commit()
    return {"user": _admin_user_json(user), "activation_token": token, "expires_at": iso(cred.expires_at)}


@router.post("/users/{user_id}/reset")
def reset_user(
    user_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.get(User, user_id)
    if user is None:
        raise NotFound()
    user.must_set_password = True
    user.password_hash = None
    revoke_user_sessions(db, user.id)
    token, cred = issue_credential(db, user, "reset", actor.user, settings)
    audit.record(db, actor=actor.user, action="identity.reset", scope_type="identity", target_id=user.id)
    db.commit()
    _hub(request).revalidate_user(user.id)
    return {"reset_token": token, "expires_at": iso(cred.expires_at)}


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: UserPatch,
    request: Request,
    actor: Actor = Depends(console_people),
    db: Session = Depends(get_db),
):
    memberships.lock_admin_roles(db)
    user = db.get(User, user_id, with_for_update=True)
    if user is None:
        raise NotFound()
    removing_admin = (body.is_admin is False and user.is_admin) or (body.is_active is False and user.is_admin)
    if removing_admin:
        active_admins = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.is_admin.is_(True), User.is_active.is_(True))
            )
            or 0
        )
        if active_admins <= 1 and user.is_active:
            raise Conflict("last_admin", "At least one active administrator must remain.")
    previously_active = user.is_active
    changes = people.patch_legacy_record(
        user,
        display_name=body.display_name,
        is_admin=body.is_admin,
        is_active=body.is_active,
        effective_on=people.site_date(get_settings(request)),
    )
    if previously_active and not user.is_active:
        user.deactivated_at = utcnow()
        revoke_user_sessions(db, user.id)
    elif not previously_active and user.is_active:
        user.deactivated_at = None
    audit.record(
        db,
        actor=actor.user,
        action="identity.update",
        **changes,
        scope_type="identity",
        target_id=user.id,
        reason=body.reason,
        **body.model_dump(exclude={"reason"}, exclude_none=True),
    )
    db.commit()
    _hub(request).revalidate_user(user.id)
    return _admin_user_json(user)


# ---- workspace tree -------------------------------------------------------


class NewWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "org"
    parent_id: uuid.UUID | None = None
    description: str = Field(default="", max_length=2000)


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    move: bool = False  # set true to apply parent_id (allows explicit null)
    archived: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


def _member_counts(db: Session) -> dict:
    return dict(
        db.execute(select(Membership.workspace_id, func.count()).group_by(Membership.workspace_id)).all()
    )


@router.get("/workspaces")
def admin_workspaces(_: Actor = Depends(console_org), db: Session = Depends(get_db)):
    counts = _member_counts(db)
    rows = db.scalars(select(Workspace).order_by(Workspace.kind, Workspace.name)).all()
    return {"workspaces": [{**workspace_json(w), "member_count": counts.get(w.id, 0)} for w in rows]}


def _validate_parent(db: Session, kind: str, parent_id: uuid.UUID | None, self_id: uuid.UUID | None = None):
    if kind != "org":
        if parent_id is not None:
            raise Invalid("invalid_parent", "Projects and groups have no parent.")
        return
    if parent_id is None:
        if db.scalar(
            select(Workspace).where(
                Workspace.kind == "org", Workspace.parent_id.is_(None), Workspace.id != self_id
            )
        ):
            raise Invalid("invalid_parent", "The organization already has a root.")
        return
    parent = db.get(Workspace, parent_id)
    if parent is None or parent.kind != "org":
        raise Invalid("invalid_parent", "Parent must be an organization unit.")
    if self_id is not None:
        parents = dict(
            db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all()
        )
        if parent_id == self_id or self_id in policy.ancestors(parents, parent_id):
            raise Invalid("cycle", "A unit cannot move beneath itself or its descendants.")


@router.post("/workspaces", status_code=201)
def create_workspace(body: NewWorkspace, actor: Actor = Depends(console_org), db: Session = Depends(get_db)):
    if body.kind not in ("org", "project"):
        raise Invalid(
            "invalid_kind", "Administrators create organization units or projects. Users create groups."
        )
    _validate_parent(db, body.kind, body.parent_id)
    ws = Workspace(
        kind=body.kind,
        name=body.name.strip(),
        description=body.description,
        parent_id=body.parent_id,
        created_by=actor.user.id,
    )
    db.add(ws)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Invalid("invalid_parent", "The organization already has a root.") from None
    audit.record(
        db,
        actor=actor.user,
        action="tree.create",
        scope_type="workspace",
        scope_id=ws.id,
        kind=body.kind,
        parent=body.parent_id,
    )
    db.commit()
    return workspace_json(ws)


@router.patch("/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: uuid.UUID,
    body: WorkspacePatch,
    request: Request,
    actor: Actor = Depends(console_org),
    db: Session = Depends(get_db),
):
    ws = db.get(Workspace, workspace_id, with_for_update=True)
    if ws is None:
        raise NotFound()
    if body.move:
        _validate_parent(db, ws.kind, body.parent_id, self_id=ws.id)
        before = ws.parent_id
        ws.parent_id = body.parent_id
        audit.record(
            db,
            actor=actor.user,
            action="tree.move",
            scope_type="workspace",
            scope_id=ws.id,
            reason=body.reason,
            before=before,
            after=body.parent_id,
        )
    if body.name is not None:
        ws.name = body.name.strip()
    if body.archived is not None and body.archived != ws.archived:
        ws.archived = body.archived
        audit.record(
            db,
            actor=actor.user,
            action="workspace.archive" if body.archived else "workspace.unarchive",
            scope_type="workspace",
            scope_id=ws.id,
            reason=body.reason,
        )
    try:
        db.commit()
    except (IntegrityError, DBAPIError):
        db.rollback()
        raise Invalid("cycle", "That move would break the organization tree.") from None
    _hub(request).revalidate_all()
    return workspace_json(ws)


# ---- memberships ----------------------------------------------------------


class MembershipBody(BaseModel):
    user_id: uuid.UUID
    role: str = "member"
    reason: str | None = Field(default=None, max_length=500)


@router.get("/workspaces/{workspace_id}/memberships")
def admin_memberships(
    workspace_id: uuid.UUID, _: Actor = Depends(console_org), db: Session = Depends(get_db)
):
    if db.get(Workspace, workspace_id) is None:
        raise NotFound()
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.username)
    ).all()
    return {"memberships": [{**user_brief(u), "role": m.role} for m, u in rows]}


@router.put("/workspaces/{workspace_id}/memberships")
def admin_set_membership(
    workspace_id: uuid.UUID,
    body: MembershipBody,
    request: Request,
    actor: Actor = Depends(console_org),
    db: Session = Depends(get_db),
):
    if body.role not in ("member", "steward"):
        raise Invalid("invalid_role", "Role must be member or steward.")
    if db.get(Workspace, workspace_id) is None or db.get(User, body.user_id) is None:
        raise NotFound()
    memberships.set_membership(
        db,
        actor=actor.user,
        workspace_id=workspace_id,
        user_id=body.user_id,
        role=body.role,
        reason=body.reason,
    )
    db.commit()
    _hub(request).revalidate_user(body.user_id)
    return {"ok": True}


@router.delete("/workspaces/{workspace_id}/memberships/{user_id}")
def admin_remove_membership(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    reason: str | None = Query(default=None, max_length=500),
    *,
    actor: Actor = Depends(console_org),
    db: Session = Depends(get_db),
):
    if not memberships.remove_membership(
        db, actor=actor.user, workspace_id=workspace_id, user_id=user_id, reason=reason
    ):
        raise NotFound()
    db.commit()
    _hub(request).revalidate_user(user_id)
    return {"ok": True}
