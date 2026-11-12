"""PO-15: access in a second unit, optionally with a position, removed automatically on an end date."""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import User, Workspace
from .. import guards
from ..actions import Appointment, Draft, appoint, set_role
from ..plan import Blocker, Plan, Warning
from ..requests import AdditionalCharge
from .common import future_date, load_person, load_space, lock_person_scope, named, today

ELIGIBLE = {"active", "on_leave"}


def lock_scope(db: Session, request: AdditionalCharge) -> None:
    lock_person_scope(db, request.person_id, {request.workspace_id})


def _blockers(db: Session, request: AdditionalCharge, person: User, unit: Workspace) -> list[Blocker]:
    blockers = []
    if person.status not in ELIGIBLE:
        blockers.append(
            Blocker("person_inactive", "Only active or on-leave people can take an additional charge.")
        )
    if unit.kind != "org" or unit.archived:
        blockers.append(Blocker("unit_unavailable", "Choose an open unit of the organisation."))
    if person.home_workspace_id == unit.id:
        blockers.append(Blocker("same_unit", "This is already the person's home unit."))
    elif policy.direct_grants(db, person.id).get(unit.id) is not None:
        message = (
            f"{person.display_name} is already a member of {unit.name}. Use Promotion to change the role."
        )
        blockers.append(Blocker("already_member", message, str(unit.id)))
    if request.position is not None:
        blockers += guards.position_holder(db, person, unit, joining=True)
    if request.position == "head" and positions.current_head(db, unit.id, acting=False) is not None:
        message = f"{unit.name} already has a Head. Use Change of head to replace them."
        blockers.append(Blocker("unit_has_head", message, str(unit.id)))
    return blockers


def _gained(db: Session, person: User, unit: Workspace) -> list[Warning]:
    before = policy.direct_grants(db, person.id)
    gained = set(policy.readable_from_grants(db, {**before, unit.id: "member"})) - set(
        policy.readable_from_grants(db, before)
    )
    names = named(db, gained)
    return [
        Warning("access_gained", f"{person.display_name} will be able to read {names[key].name}.", str(key))
        for key in sorted(gained, key=lambda key: names[key].name)
    ]


def draft(db: Session, request: AdditionalCharge, settings: Settings) -> Draft:
    person = load_person(db, request.person_id)
    unit = load_space(db, request.workspace_id)
    result = Draft(person)
    result.blockers += _blockers(db, request, person, unit)
    result.blockers += future_date(request.ends_on, settings, "the end date of the additional charge")
    result.actions.append(set_role(person, unit, None, request.role))
    item = Appointment(
        request.position or "charge", today(settings), ends_on=request.ends_on, revert_role="none"
    )
    result.actions.append(appoint(person, unit, item))
    result.warnings += _gained(db, person, unit)
    if request.ends_on is not None:
        message = f"On {request.ends_on.isoformat()} this access ends and the membership is removed."
        result.warnings.append(Warning("ends_automatically", message, str(unit.id)))
    return result


def build(db: Session, request: AdditionalCharge, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """The membership, the recorded charge or position, and any end date."""
    return draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(
    db: Session, actor: User, plan: Plan, request: AdditionalCharge, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
