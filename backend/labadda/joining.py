"""Resolve verified affiliations and identities without widening private workspace access."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .errors import Conflict, Invalid
from .models import JoinRequest, User, Workspace


def organisation_unit(db: Session, unit_id: uuid.UUID) -> Workspace:
    """Only an active organisation unit may be an applicant's home affiliation."""
    unit = db.get(Workspace, unit_id, populate_existing=True)
    if unit is None or unit.kind != "org" or unit.archived:
        raise Invalid(
            "invalid_unit", "Choose an active organisation unit; the previous selection is unavailable."
        )
    return unit


def target_plan(
    db: Session, request: JoinRequest, chosen_id: uuid.UUID | None, custom_name: str | None
) -> tuple[Workspace, str | None]:
    """Require an explicit affiliation, never silently substitute the organisation root."""
    if chosen_id:
        return organisation_unit(db, chosen_id), None
    if not custom_name and request.unit_id:
        return organisation_unit(db, request.unit_id), None
    name = (custom_name or request.unit_name or "").strip()
    if not name:
        raise Invalid("affiliation_required", "Select the verified organisation unit before approval.")
    matches = db.scalars(
        select(Workspace)
        .where(Workspace.kind == "org", func.lower(Workspace.name) == name.lower())
        .order_by(Workspace.archived, Workspace.id)
        .limit(2)
    ).all()
    active = [unit for unit in matches if not unit.archived]
    if len(active) > 1:
        raise Invalid("ambiguous_unit", "Several units share this name. Select the verified unit explicitly.")
    if active:
        return active[0], None
    if matches:
        raise Invalid("invalid_unit", "This organisation unit is archived. Select an active unit.")
    root = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None)))
    if root is None or root.archived:
        raise Invalid("invalid_unit", "Create an active organisation root before approving a new unit.")
    return root, name


def create_unit(db: Session, parent: Workspace, name: str, actor: User) -> Workspace:
    """Create the administrator-confirmed unit with same-transaction audit history."""
    unit = Workspace(kind="org", name=name, parent_id=parent.id, created_by=actor.id)
    db.add(unit)
    db.flush()
    audit.record(
        db,
        actor=actor,
        action="tree.create",
        scope_type="workspace",
        scope_id=unit.id,
        kind="org",
        parent=parent.id,
        reason="Verified voluntary application affiliation",
    )
    return unit


def check_identity(db: Session, username: str, employee_no: str | None) -> None:
    """Recheck every final identity, including employee numbers unchanged since submission."""
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise Conflict(
            "username_taken", "A staff account now uses this username. Review the application again."
        )
    if (
        employee_no
        and db.scalar(select(User.id).where(func.lower(User.employee_no) == employee_no.lower())) is not None
    ):
        raise Conflict("employee_no_taken", "A staff record already uses this employee number.")
