"""Membership mutations shared by administration and collaborative groups."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import audit, policy, positions
from .errors import Conflict
from .models import Membership, User

STEWARD_LOCK = 7_310_001  # advisory-lock namespace for last-steward checks
ADMIN_LOCK = 7_310_002


def lock_workspace_roles(db: Session, workspace_id: uuid.UUID) -> None:
    db.execute(
        text("select pg_advisory_xact_lock(:ns, hashtext(:ws))"),
        {"ns": STEWARD_LOCK, "ws": str(workspace_id)},
    )


def lock_admin_roles(db: Session) -> None:
    db.execute(text("select pg_advisory_xact_lock(:ns)"), {"ns": ADMIN_LOCK})


def active_steward_count(db: Session, workspace_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.role == "steward",
                User.is_active.is_(True),
            )
        )
        or 0
    )


def direct_role(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> str | None:
    return db.scalar(
        select(Membership.role).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
    )


def set_membership(
    db: Session,
    *,
    actor,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    protect_last_steward: bool = False,
    reason: str | None = None,
) -> Membership:
    lock_workspace_roles(db, workspace_id)
    m = db.scalar(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
    )
    before = m.role if m else None
    if m is None:
        m = Membership(workspace_id=workspace_id, user_id=user_id, role=role)
        db.add(m)
    else:
        if (
            protect_last_steward
            and before == "steward"
            and role != "steward"
            and active_steward_count(db, workspace_id) <= 1
        ):
            raise Conflict("last_steward", "Make another member a steward first.")
        m.role = role
        if before == "steward" and role != "steward":
            # PO-13: a Head or Deputy is always a steward, so demotion ends the position.
            positions.end_held(
                db, user_id, workspace_id, actor=actor, reason=reason, kinds=("head", "deputy")
            )
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="membership.set",
        scope_type="workspace",
        scope_id=workspace_id,
        target_id=user_id,
        reason=reason,
        before=before,
        after=role,
    )
    return m


def remove_membership(
    db: Session,
    *,
    actor,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    protect_last_steward: bool = False,
    reason: str | None = None,
) -> bool:
    lock_workspace_roles(db, workspace_id)
    m = db.scalar(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id)
    )
    if m is None:
        return False
    if protect_last_steward and m.role == "steward" and active_steward_count(db, workspace_id) <= 1:
        raise Conflict("last_steward", "Make another member a steward first, or archive the group.")
    positions.end_held(db, user_id, workspace_id, actor=actor, reason=reason)
    db.delete(m)
    user = db.get(User, user_id)
    if user is not None and user.home_workspace_id == workspace_id:
        user.home_workspace_id = None
    audit.record(
        db,
        actor=actor,
        action="membership.remove",
        scope_type="workspace",
        scope_id=workspace_id,
        target_id=user_id,
        reason=reason,
        before=m.role,
    )
    db.flush()
    return True


def readable_now(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    return policy.can_read(db, user, workspace_id)
