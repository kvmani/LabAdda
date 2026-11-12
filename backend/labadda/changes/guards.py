"""Metadata-only guards shared by staff-change builders."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import policy
from ..models import Membership, User, Workspace
from .plan import Blocker, Warning


def unique_employee_number(
    db: Session, value: str | None, person_id: uuid.UUID | None = None
) -> list[Blocker]:
    """Block duplicate employee numbers without exposing the other person's record."""
    if value is None:
        return []
    query = select(User.id).where(User.employee_no == value)
    if person_id is not None:
        query = query.where(User.id != person_id)
    if db.scalar(query.limit(1)) is None:
        return []
    return [Blocker("duplicate_employee", "That employee number is already assigned to another person.")]


def last_administrator(db: Session, person: User) -> list[Blocker]:
    """PO-08: at least one active administrator remains after a person stops signing in."""
    if not (person.is_admin and person.is_active):
        return []
    others = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.is_admin.is_(True), User.is_active.is_(True), User.id != person.id)
    )
    if others:
        return []
    return [Blocker("last_admin", "At least one active administrator must remain. Appoint another first.")]


def not_self(person: User, actor_id: uuid.UUID) -> list[Blocker]:
    """Ending one's own sign-in would end the session making the change."""
    if person.id != actor_id:
        return []
    return [Blocker("self_change", "Ask another administrator to make this change to your own account.")]


def unit_branch(db: Session, unit_id: uuid.UUID) -> set[uuid.UUID]:
    """The unit and every organisation unit below it."""
    parents = dict(db.execute(select(Workspace.id, Workspace.parent_id).where(Workspace.kind == "org")).all())
    return {space for space in parents if space == unit_id or unit_id in policy.ancestors(parents, space)}


def position_holder(db: Session, holder: User, unit: Workspace, *, joining: bool = False) -> list[Blocker]:
    """PO-08: a holder is active and belongs to the unit (home in its branch, a membership, or
    ``joining`` it in the same plan)."""
    name = holder.display_name
    if holder.status != "active":
        return [
            Blocker("holder_inactive", f"{name} is not active and cannot hold a position.", str(holder.id))
        ]
    if unit.kind != "org" or unit.archived:
        return [Blocker("unit_unavailable", "Positions exist only in open units of the organisation.")]
    if joining or holder.home_workspace_id in unit_branch(db, unit.id):
        return []
    if policy.direct_grants(db, holder.id).get(unit.id) is not None:
        return []
    message = f"{name} does not belong to {unit.name}. Transfer them or give an additional charge first."
    return [Blocker("holder_outside_unit", message, str(holder.id))]


def group_successor(db: Session, space: Workspace, successor_id: uuid.UUID) -> User | None:
    """A project or group successor must be one of its own active members (PO-08)."""
    successor = db.get(User, successor_id)
    if successor is None or not successor.is_active or successor.status != "active":
        return None
    return successor if policy.direct_grants(db, successor.id).get(space.id) is not None else None


def active_stewards(db: Session, workspace_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.workspace_id == workspace_id, Membership.role == "steward", User.is_active.is_(True)
        )
    )
    return set(rows)


def steward_gap(
    space: Workspace, acknowledged: bool, *, remaining: set[uuid.UUID], has_members: bool
) -> list[Blocker | Warning]:
    """PO-08: units may lose their last steward only when acknowledged; projects and groups never."""
    if remaining:
        return []
    target = str(space.id)
    if space.kind != "org":
        if not has_members:
            return []
        message = f"{space.name} would have no steward. Choose a successor from its members."
        return [Blocker("group_needs_steward", message, target)]
    if acknowledged:
        return [Warning("unit_without_steward", f"{space.name} will have no active steward.", target)]
    message = f"{space.name} would have no active steward. Tick the acknowledgement to continue."
    return [Blocker("unit_without_steward", message, target)]
