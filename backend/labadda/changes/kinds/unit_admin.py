"""PO-24: appoint or withdraw a unit administrator. Only site administrators may use these kinds."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import audit, memberships
from ...config import Settings
from ...errors import Forbidden
from ...models import UnitAdminGrant, User, Workspace
from ...security import utcnow
from ..actions import Action, Draft
from ..plan import Blocker, Plan, Snapshot, Step
from ..requests import GrantUnitAdmin, RevokeUnitAdmin
from .common import load_person, load_space

type Request = GrantUnitAdmin | RevokeUnitAdmin


def lock_scope(db: Session, request: Request) -> set[uuid.UUID]:
    """Appointments serialize with the unit's other role changes."""
    memberships.lock_workspace_roles(db, request.unit_id)
    return {request.unit_id}


def _current(db: Session, person_id: uuid.UUID, unit_id: uuid.UUID) -> UnitAdminGrant | None:
    return db.scalar(
        select(UnitAdminGrant)
        .where(
            UnitAdminGrant.user_id == person_id,
            UnitAdminGrant.workspace_id == unit_id,
            UnitAdminGrant.revoked_at.is_(None),
        )
        .with_for_update()
    )


def _grant_blockers(person: User, unit: Workspace, held: bool) -> list[Blocker]:
    blockers = []
    if person.is_admin:
        blockers.append(Blocker("already_admin", "A site administrator already administers every unit."))
    elif not person.is_active or person.status != "active":
        blockers.append(Blocker("person_inactive", "Only an active person can be appointed."))
    if unit.kind != "org" or unit.archived:
        blockers.append(Blocker("unit_unavailable", "Choose an open unit of the organisation."))
    if held:
        blockers.append(Blocker("no_change", f"{person.display_name} already administers {unit.name}."))
    return blockers


def _action(person: User, unit: Workspace, grant: bool) -> Action:
    name = person.display_name
    summary = (
        f"Make {name} a unit administrator of {unit.name}"
        if grant
        else f"Withdraw {name} as a unit administrator of {unit.name}"
    )
    step = Step(
        "identity",
        str(person.id),
        summary,
        Snapshot({"unit_administrator_of": None if grant else unit.name}),
        Snapshot({"unit_administrator_of": unit.name if grant else None}),
    )

    def run(db: Session, actor: User, reason: str) -> None:
        row = _current(db, person.id, unit.id)
        if grant:
            db.add(UnitAdminGrant(user_id=person.id, workspace_id=unit.id, granted_by=actor.id))
        elif row is not None:
            row.revoked_at = utcnow()
        # The audit event is written with the grant itself, so no appointment exists unrecorded.
        audit.record(
            db,
            actor=actor,
            action="unit_admin.grant" if grant else "unit_admin.revoke",
            scope_type="workspace",
            scope_id=unit.id,
            target_id=person.id,
            reason=reason,
        )

    return Action(step, run)


def draft(db: Session, request: Request) -> Draft:
    person = load_person(db, request.person_id)
    unit = load_space(db, request.unit_id)
    grant = isinstance(request, GrantUnitAdmin)
    held = _current(db, person.id, unit.id) is not None
    result = Draft(person, affected_people=0)
    if grant:
        result.blockers += _grant_blockers(person, unit, held)
    elif not held:
        message = f"{person.display_name} does not administer {unit.name}."
        result.blockers.append(Blocker("no_change", message))
    result.actions.append(_action(person, unit, grant))
    return result


def build(db: Session, request: Request, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return draft(db, request).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(
    db: Session, actor: User, plan: Plan, request: Request, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request)
    if not (actor.is_admin and actor.is_active):
        raise Forbidden("admin_required", "Only a site administrator can appoint unit administrators.")
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
