"""PO-16: long leave with an expected return date, optional sign-in block and acting replacements."""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import UnitPosition, User
from .. import guards
from ..actions import Appointment, Draft, appoint, set_role, set_status
from ..plan import Blocker, Plan, Warning
from ..requests import ActingCover, Leave
from .common import future_date, load_person, load_space, lock_person_scope, today


def lock_scope(db: Session, request: Leave) -> None:
    lock_person_scope(db, request.person_id)


def _cover(db: Session, result: Draft, request: Leave, cover: ActingCover, settings: Settings) -> None:
    person = result.person
    row = db.get(UnitPosition, cover.position_id, populate_existing=True)
    if row is None or row.user_id != person.id or row.ended_at is not None or row.position == "charge":
        message = "Choose a position the person currently holds."
        result.blockers.append(Blocker("not_their_position", message, str(cover.position_id)))
        return
    unit = load_space(db, row.workspace_id)
    successor = load_person(db, cover.successor_id)
    if successor.id == person.id:
        result.blockers.append(Blocker("invalid_request", "Choose someone else to act for them."))
        return
    result.blockers += guards.position_holder(db, successor, unit)
    if row.position == "head" and positions.current_head(db, unit.id, acting=True) is not None:
        message = f"{unit.name} already has an acting Head. Change that appointment first."
        result.blockers.append(Blocker("unit_has_acting_head", message, str(unit.id)))
    before = policy.direct_grants(db, successor.id).get(unit.id)
    if before != "steward":
        result.actions.append(set_role(successor, unit, before, "steward"))
    item = Appointment(
        row.position,
        today(settings),
        ends_on=request.expected_return_on,
        acting=True,
        revert_role=positions.role_before(db, successor.id, unit.id),
        covers_id=row.id,
    )
    result.actions.append(appoint(successor, unit, item))
    result.affected_people += 1


def draft(db: Session, request: Leave, settings: Settings, actor_id: uuid.UUID) -> Draft:
    person = load_person(db, request.person_id)
    result = Draft(person, affected_people=1 if request.block_sign_in else 0)
    if person.status != "active":
        result.blockers.append(Blocker("person_unavailable", "Only active people can go on leave."))
    result.blockers += future_date(request.expected_return_on, settings, "the expected return date")
    if request.block_sign_in:
        result.blockers += guards.last_administrator(db, person) + guards.not_self(person, actor_id)
    result.actions.append(
        set_status(
            person,
            "on_leave",
            today(settings),
            leave_sign_in=not request.block_sign_in,
            expected_return_on=request.expected_return_on,
        )
    )
    for cover in request.acting:
        _cover(db, result, request, cover, settings)
    covered = {cover.position_id for cover in request.acting}
    for row in positions.current(db, user_id=person.id):
        if row.position != "charge" and row.id not in covered:
            unit = load_space(db, row.workspace_id)
            message = f"{person.display_name} stays {positions.title(row)} of {unit.name} with no one acting."
            result.warnings.append(Warning("position_uncovered", message, str(row.id)))
    return result


def build(db: Session, request: Leave, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Status, sign-in and each acting appointment, which ends on the expected return date."""
    return draft(db, request, settings, actor_id).plan(
        request.kind, actor_id, request.model_dump(mode="json")
    )


def apply(
    db: Session, actor: User, plan: Plan, request: Leave, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings, actor.id)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
