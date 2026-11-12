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
from .models import Membership, UnitAdminGrant, UsageReaderGrant, User, Workspace
from .security import utcnow

type Scope = frozenset[uuid.UUID] | None  # a unit administrator's units; None means no limit


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
    return readable_from_grants(db, direct_grants(db, user.id))


def readable_from_grants(db: Session, grants: dict[uuid.UUID, str]) -> dict[uuid.UUID, str | None]:
    """Apply the upward-only rule to a set of direct grants, current or proposed."""
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


CONSOLE_SECTIONS = (
    "overview",
    "people",
    "org",
    "activity",
    "health",
    "storage",
    "backups",
    "audit",
    "events",
    "settings",
    "help",
)
READER_SECTIONS = ("overview", "activity", "health", "storage", "backups", "events")


def can_read_usage(db: Session, user: User) -> bool:
    """Resolve current operational delegation without granting content access."""
    if not user.is_active:
        return False
    return (
        user.is_admin
        or db.scalar(
            select(UsageReaderGrant.user_id).where(
                UsageReaderGrant.user_id == user.id, UsageReaderGrant.expires_at > utcnow()
            )
        )
        is not None
    )


UNIT_ADMIN_SECTIONS = ("people", "org")


def unit_admin_roots(db: Session, user: User) -> frozenset[uuid.UUID]:
    """Open units the person is currently appointed to administer; nothing for an inactive person."""
    if not user.is_active:
        return frozenset()
    rows = db.scalars(
        select(UnitAdminGrant.workspace_id)
        .join(Workspace, Workspace.id == UnitAdminGrant.workspace_id)
        .where(
            UnitAdminGrant.user_id == user.id,
            UnitAdminGrant.revoked_at.is_(None),
            Workspace.kind == "org",
            Workspace.archived.is_(False),
        )
    )
    return frozenset(rows)


def people_scope(db: Session, user: User) -> frozenset[uuid.UUID]:
    """Unit IDs whose people and structure the person may administer, read from grants as they are now.

    Site administrators reach every unit; a unit administrator reaches the unit they were appointed
    to and the units below it, never a parent, a sibling or a project or group.
    """
    if not user.is_active:
        return frozenset()
    parents = _org_parents(db)
    if user.is_admin:
        return frozenset(parents)
    roots = unit_admin_roots(db, user)
    if not roots:
        return frozenset()
    return frozenset(
        unit for unit in parents if unit in roots or any(anc in roots for anc in ancestors(parents, unit))
    )


def restricted_scope(db: Session, user: User) -> Scope:
    """The scope a unit administrator is held to, or ``None`` for a site administrator (no limit)."""
    return None if user.is_admin and user.is_active else people_scope(db, user)


def is_unit_admin(db: Session, user: User) -> bool:
    return not user.is_admin and bool(unit_admin_roots(db, user))


def console_sections(db: Session, user: User) -> tuple[str, ...]:
    """Return only the console sections available under current authority."""
    if not user.is_active:
        return ()
    if user.is_admin:
        return CONSOLE_SECTIONS
    granted = set(READER_SECTIONS) if can_read_usage(db, user) else set()
    if is_unit_admin(db, user):
        granted |= set(UNIT_ADMIN_SECTIONS)
    return tuple(section for section in CONSOLE_SECTIONS if section in granted)
