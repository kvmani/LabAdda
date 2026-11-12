"""PO-14: replace a unit's Head or a Deputy, permanently or as an acting appointment with an end date."""

import uuid

from sqlalchemy.orm import Session

from ... import memberships, policy, positions
from ...config import Settings
from ...models import UnitPosition, User, Workspace
from .. import guards
from ..actions import Appointment, Draft, appoint, end_position, set_role
from ..plan import Blocker, Plan
from ..requests import ChangeAuthority
from .common import future_date, load_person, load_space, today

PRESENT = "active"


def lock_scope(db: Session, request: ChangeAuthority) -> None:
    """One unit's role lock covers its positions; the successor row is locked by the service."""
    memberships.lock_workspace_roles(db, request.workspace_id)


def _outgoing(
    db: Session, request: ChangeAuthority, unit: Workspace
) -> tuple[list[UnitPosition], UnitPosition | None]:
    """Rows this appointment replaces, and the absent Head an acting Head covers (if any)."""
    if request.position == "deputy":
        if request.replace_person_id is None:
            return [], None
        rows = [
            row
            for row in positions.current(db, user_id=request.replace_person_id, workspace_id=unit.id)
            if row.position == "deputy"
        ]
        return rows, None
    substantive = positions.current_head(db, unit.id, acting=False)
    acting = positions.current_head(db, unit.id, acting=True)
    replaced = [row for row in (acting,) if row is not None]
    if substantive is None:
        return replaced, None
    holder = db.get(User, substantive.user_id)
    if request.acting and holder is not None and holder.status != PRESENT:
        return replaced, substantive
    return [substantive, *replaced], None


def _blockers(db: Session, request: ChangeAuthority, unit: Workspace, successor: User, settings: Settings):
    blockers = guards.position_holder(db, successor, unit)
    blockers += future_date(request.ends_on, settings, "the end date of the acting appointment")
    held = positions.current(db, user_id=successor.id, workspace_id=unit.id)
    if any(row.position == request.position and row.acting == request.acting for row in held):
        message = f"{successor.display_name} already holds this position."
        blockers.append(Blocker("already_holds", message, str(successor.id)))
    if request.replace_person_id is not None and request.position == "head":
        blockers.append(Blocker("invalid_request", "The current Head is replaced automatically."))
    return blockers


def draft(db: Session, request: ChangeAuthority, settings: Settings) -> Draft:
    unit = load_space(db, request.workspace_id)
    successor = load_person(db, request.successor_id)
    result = Draft(successor)
    result.blockers += _blockers(db, request, unit, successor, settings)
    outgoing, covered = _outgoing(db, request, unit)
    if request.replace_person_id is not None and request.position == "deputy" and not outgoing:
        message = "That person is not a Deputy of this unit."
        result.blockers.append(Blocker("not_a_deputy", message, str(request.replace_person_id)))
    people = 1
    for row in outgoing:
        holder = load_person(db, row.user_id)
        reverting = row.acting and holder.id != successor.id
        result.actions.append(end_position(holder, row, unit, revert=reverting))
        role = policy.direct_grants(db, holder.id).get(unit.id)
        if (
            not row.acting
            and holder.id != successor.id
            and request.outgoing_role == "member"
            and role == "steward"
        ):
            result.actions.append(set_role(holder, unit, "steward", "member"))
        people += holder.id != successor.id
    before = policy.direct_grants(db, successor.id).get(unit.id)
    if before != "steward":
        result.actions.append(set_role(successor, unit, before, "steward"))
    item = Appointment(
        request.position,
        today(settings),
        ends_on=request.ends_on,
        acting=request.acting,
        revert_role=positions.role_before(db, successor.id, unit.id) if request.acting else None,
        covers_id=covered.id if covered else None,
    )
    result.actions.append(appoint(successor, unit, item))
    result.affected_people = people
    return result


def build(db: Session, request: ChangeAuthority, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Outgoing holders, the successor's steward role and the appointment, in order."""
    return draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(
    db: Session, actor: User, plan: Plan, request: ChangeAuthority, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
