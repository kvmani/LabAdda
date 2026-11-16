"""Stewards appoint child-unit representatives without granting moderation."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import audit, memberships, policy
from ..deps import Actor, current_actor, get_db
from ..errors import Conflict, Invalid, NotFound
from ..models import ContributionDelegation, User
from ..security import utcnow
from ..serialize import iso, user_brief, users_by_id
from .todos import _actor, _scope_locks

router = APIRouter(tags=["contributions"])


class Appointment(BaseModel):
    """An explicit, reasoned appointment at the source unit's immediate parent."""

    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    expires_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


class Revocation(BaseModel):
    """Optimistic concurrency protects a reviewed authority change."""

    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


def _json(users: dict, grant: ContributionDelegation) -> dict:
    return {
        "id": str(grant.id),
        "user": user_brief(users.get(grant.user_id)),
        "source_id": str(grant.source_id),
        "destination_id": str(grant.destination_id),
        "expires_at": iso(grant.expires_at),
        "revision": grant.revision,
    }


@router.get("/workspaces/{workspace_id}/delegations")
def list_delegations(
    workspace_id: uuid.UUID,
    request: Request,
    *,
    search: str = Query(default="", max_length=120),
    offset: int = Query(default=0, ge=0),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> dict:
    """Expose appointment controls only to the selected workspace's current steward."""
    user = _actor(request, actor, db)
    access = policy.require_moderate(db, user, workspace_id)
    grants = db.scalars(
        select(ContributionDelegation)
        .where(
            or_(
                ContributionDelegation.source_id == workspace_id,
                ContributionDelegation.destination_id == workspace_id,
            ),
            ContributionDelegation.revoked_at.is_(None),
            or_(ContributionDelegation.expires_at.is_(None), ContributionDelegation.expires_at > utcnow()),
        )
        .order_by(ContributionDelegation.created_at, ContributionDelegation.id)
        .offset(offset)
        .limit(101)
    ).all()
    candidates = db.scalars(
        select(User)
        .where(User.id.in_(policy.eligible_reader_ids(db, access.workspace)))
        .where(User.display_name.ilike("%" + search + "%"))
        .order_by(User.display_name, User.id)
        .limit(100)
    ).all()
    users = users_by_id(db, {grant.user_id for grant in grants[:100]})
    return {
        "delegations": [_json(users, grant) for grant in grants[:100]],
        "has_more": len(grants) > 100,
        "candidates": [user_brief(user) for user in candidates],
        "destination_id": str(access.workspace.parent_id) if access.workspace.parent_id else None,
    }


@router.post("/workspaces/{workspace_id}/delegations", status_code=201)
def appoint(
    workspace_id: uuid.UUID,
    body: Appointment,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> dict:
    """Delegate at one parent only, checking current steward and recipient membership."""
    memberships.lock_admin_roles(db)
    memberships.lock_workspace_roles(db, workspace_id)
    _scope_locks(db, workspace_id)
    _actor(request, actor, db, True)
    source = policy.require_moderate(db, actor.user, workspace_id).workspace
    if source.kind != "org" or source.parent_id is None or source.archived:
        raise Invalid("invalid_source", "Choose an active organisation unit with a parent.")
    if body.expires_at is not None and (body.expires_at.tzinfo is None or body.expires_at <= utcnow()):
        raise Invalid("invalid_expiry", "Choose a future expiry with a time zone.")
    if body.user_id not in policy.eligible_reader_ids(db, source):
        raise Invalid("invalid_representative", "Choose an active member of this unit or its descendants.")
    current = db.scalar(
        select(ContributionDelegation).where(
            ContributionDelegation.source_id == source.id,
            ContributionDelegation.destination_id == source.parent_id,
            ContributionDelegation.user_id == body.user_id,
            ContributionDelegation.revoked_at.is_(None),
            or_(ContributionDelegation.expires_at.is_(None), ContributionDelegation.expires_at > utcnow()),
        )
    )
    if current:
        raise Conflict("already_delegated", "This person already represents this unit at its parent.")
    grant = ContributionDelegation(
        source_id=source.id,
        destination_id=source.parent_id,
        user_id=body.user_id,
        granted_by=actor.id,
        expires_at=body.expires_at,
    )
    db.add(grant)
    db.flush()
    audit.record(
        db,
        actor=actor.user,
        action="contribution.appoint",
        scope_type="workspace",
        scope_id=source.id,
        target_id=body.user_id,
        reason=body.reason,
        before=None,
        after={"destination_id": str(source.parent_id), "expires_at": iso(body.expires_at)},
    )
    db.commit()
    request.app.state.hub.revalidate_user(body.user_id)
    return _json(users_by_id(db, [grant.user_id]), grant)


@router.post("/workspaces/{workspace_id}/delegations/{grant_id}/revoke")
def revoke(
    workspace_id: uuid.UUID,
    grant_id: uuid.UUID,
    *,
    body: Revocation,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
) -> dict:
    """Either the source or destination steward can revoke a reviewed appointment."""
    memberships.lock_admin_roles(db)
    memberships.lock_workspace_roles(db, workspace_id)
    _scope_locks(db, workspace_id)
    _actor(request, actor, db, True)
    policy.require_moderate(db, actor.user, workspace_id)
    grant = db.get(ContributionDelegation, grant_id, with_for_update=True)
    if grant is None or workspace_id not in (grant.source_id, grant.destination_id):
        raise NotFound()
    if grant.revision != body.revision:
        raise Conflict("stale_revision", "This appointment changed. Reload and review it again.")
    grant.revoked_at = utcnow()
    grant.revision += 1
    audit.record(
        db,
        actor=actor.user,
        action="contribution.revoke",
        scope_type="workspace",
        scope_id=workspace_id,
        target_id=grant.user_id,
        reason=body.reason,
        before={"source_id": str(grant.source_id), "destination_id": str(grant.destination_id)},
        after=None,
    )
    db.commit()
    request.app.state.hub.revalidate_user(grant.user_id)
    return {"revoked": True, "revision": grant.revision}
