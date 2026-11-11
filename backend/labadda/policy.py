"""Shared authorization policy (S2).

Every content endpoint resolves access through this module. Rules:

* Grants are direct memberships resolved by stable IDs.
* In the organization tree, a direct grant on a node gives inherited
  member access to that node's ancestors (grants flow upward only).
* Projects and collaborative groups have no hierarchy: only direct grants.
* Steward authority (pin, official notice, moderate, posting policy) is
  direct only and applies to the target workspace only.
* An org administrator has no content access without a grant.
* Archived spaces stay readable by eligible members but accept no shared
  mutations. Read-only spaces accept mutations from direct stewards only.
* Out-of-scope requests raise ``NotFound`` (uniform 404); visible but
  forbidden actions raise ``Forbidden`` (403).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import Forbidden, NotFound
from .models import Membership, User, Workspace


@dataclass(frozen=True)
class Access:
    workspace: Workspace
    direct_role: str | None
    can_read: bool
    can_write: bool
    can_moderate: bool

    @property
    def inherited(self) -> bool:
        return self.direct_role is None and self.can_read


def direct_grants(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = db.execute(select(Membership.workspace_id, Membership.role).where(Membership.user_id == user_id))
    return dict(rows.all())


def _org_parents(db: Session) -> dict[uuid.UUID, uuid.UUID | None]:
    rows = db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org"))
    return dict(rows.all())


def ancestors(parents: dict[uuid.UUID, uuid.UUID | None], ws_id: uuid.UUID) -> list[uuid.UUID]:
    """Return ancestors of ``ws_id`` nearest first (excluding itself)."""
    out: list[uuid.UUID] = []
    seen = {ws_id}
    current = parents.get(ws_id)
    while current is not None and current not in seen:
        out.append(current)
        seen.add(current)
        current = parents.get(current)
    return out


def readable_workspace_ids(db: Session, user: User) -> dict[uuid.UUID, str | None]:
    """Map each readable workspace ID to the user's direct role there (or None if inherited)."""
    if not user.is_active:
        return {}
    grants = direct_grants(db, user.id)
    if not grants:
        return {}
    parents = _org_parents(db)
    result: dict[uuid.UUID, str | None] = dict(grants)
    for ws_id in grants:
        if ws_id in parents:  # org node: grant flows upward
            for anc in ancestors(parents, ws_id):
                result.setdefault(anc, None)
    return result


def resolve(db: Session, user: User, workspace_id: uuid.UUID) -> Access | None:
    if not user.is_active:
        return None
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        return None
    readable = readable_workspace_ids(db, user)
    if ws.id not in readable:
        return None
    role = readable[ws.id]
    steward = role == "steward"
    writable = not ws.archived and (ws.posting_policy == "open" or steward)
    return Access(workspace=ws, direct_role=role, can_read=True, can_write=writable, can_moderate=steward)


def require_read(db: Session, user: User, workspace_id: uuid.UUID) -> Access:
    access = resolve(db, user, workspace_id)
    if access is None:
        raise NotFound()
    return access


def require_write(db: Session, user: User, workspace_id: uuid.UUID) -> Access:
    access = require_read(db, user, workspace_id)
    if access.workspace.archived:
        raise Forbidden("workspace_archived", "This workspace is archived and read-only.")
    if not access.can_write:
        raise Forbidden("workspace_read_only", "This workspace is read-only for members.")
    return access


def require_moderate(db: Session, user: User, workspace_id: uuid.UUID) -> Access:
    access = require_read(db, user, workspace_id)
    if not access.can_moderate:
        raise Forbidden("steward_required", "Only a steward of this workspace can do that.")
    return access


def eligible_reader_ids(db: Session, workspace: Workspace) -> set[uuid.UUID]:
    """Active users who can currently read ``workspace``."""
    if workspace.kind == "org":
        parents = _org_parents(db)
        scope = {workspace.id}
        # Every org node that has ``workspace`` as ancestor-or-self.
        for ws_id in parents:
            if workspace.id in ancestors(parents, ws_id):
                scope.add(ws_id)
    else:
        scope = {workspace.id}
    rows = db.execute(
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id.in_(scope), User.is_active.is_(True))
    )
    return {uid for (uid,) in rows}


def can_read(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    return resolve(db, user, workspace_id) is not None


def direct_grants_for_workspace(db: Session, workspace_id: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = db.execute(
        select(Membership.user_id, Membership.role).where(Membership.workspace_id == workspace_id)
    )
    return dict(rows.all())
