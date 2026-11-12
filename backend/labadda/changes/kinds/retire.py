"""PO-17: retire or leave now: positions end with successors, memberships go, sign-in ends.

The plan lists every workspace where the person is the last steward; a project or group with
other members needs a successor chosen from those members, a unit needs a successor or an
explicit acknowledgement. Open shared tasks are counted per workspace and its stewards notified.
"""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import UnitPosition, User, Workspace
from .. import guards
from ..actions import Appointment, Draft, appoint, end_position, set_role, set_status
from ..plan import Blocker, Plan, Warning
from ..requests import Retire, Successor
from .common import (
    future_date,
    load_person,
    lock_person_scope,
    named,
    notify_stewards,
    task_warnings,
    today,
)

DEPARTED = {"retired", "left"}


def lock_scope(db: Session, request: Retire) -> None:
    lock_person_scope(db, request.person_id, {item.workspace_id for item in request.successors})


def _successor_steward(db: Session, result: Draft, space: Workspace, successor: User) -> None:
    before = policy.direct_grants(db, successor.id).get(space.id)
    if before != "steward":
        result.actions.append(set_role(successor, space, before, "steward"))
        result.affected_people += 1


def _take_position(
    db: Session, result: Draft, row: UnitPosition, space: Workspace, item: Successor, settings: Settings
) -> None:
    successor = load_person(db, item.successor_id)
    result.blockers += guards.position_holder(db, successor, space)
    result.blockers += future_date(item.ends_on, settings, "the end date of the acting appointment")
    if row.position == "head" and item.acting and positions.current_head(db, space.id, acting=True):
        message = f"{space.name} already has an acting Head. Change that appointment first."
        result.blockers.append(Blocker("unit_has_acting_head", message, str(space.id)))
    revert = positions.role_before(db, successor.id, space.id) if item.acting else None
    _successor_steward(db, result, space, successor)
    appointment = Appointment(row.position, today(settings), item.ends_on, item.acting, revert)
    result.actions.append(appoint(successor, space, appointment))


def _positions(
    db: Session, result: Draft, request: Retire, spaces: dict[uuid.UUID, Workspace], settings: Settings
) -> set[uuid.UUID]:
    """End every position; Head and Deputy need a successor or the acknowledgement."""
    chosen = {item.workspace_id: item for item in request.successors}
    handled = set()
    for row in positions.current(db, user_id=result.person.id):
        space = spaces[row.workspace_id]
        result.actions.append(end_position(result.person, row, space))
        if row.position == "charge":
            continue
        handled.add(space.id)
        if space.id in chosen:
            _take_position(db, result, row, space, chosen[space.id], settings)
            continue
        label = positions.title(row)
        if request.acknowledge_no_steward:
            message = f"{space.name} will have no {label} until one is appointed."
            result.warnings.append(Warning("position_vacant", message, str(space.id)))
        else:
            message = f"Choose who takes over as {label} of {space.name}, or tick the acknowledgement."
            result.blockers.append(Blocker("position_needs_successor", message, str(space.id)))
    return handled


def _last_stewards(
    db: Session,
    result: Draft,
    request: Retire,
    spaces: dict[uuid.UUID, Workspace],
    grants: dict[uuid.UUID, str],
    handled: set[uuid.UUID],
) -> None:
    """List each workspace the person is the last active steward of, and settle it."""
    chosen = {item.workspace_id: item for item in request.successors}
    person = result.person
    for workspace_id, role in grants.items():
        space = spaces[workspace_id]
        if role != "steward" or guards.active_stewards(db, workspace_id) - {person.id}:
            continue
        message = f"{person.display_name} is the last steward of {space.name}."
        result.warnings.append(Warning("last_steward", message, str(workspace_id)))
        if workspace_id in handled:
            continue
        item = chosen.get(workspace_id)
        if item is not None and space.kind != "org":
            successor = guards.group_successor(db, space, item.successor_id)
            if successor is None:
                message = f"Choose the new steward of {space.name} from its active members."
                result.blockers.append(Blocker("successor_not_member", message, str(workspace_id)))
                continue
            _successor_steward(db, result, space, successor)
            continue
        if item is not None:
            successor = load_person(db, item.successor_id)
            result.blockers += guards.position_holder(db, successor, space)
            _successor_steward(db, result, space, successor)
            continue
        others = bool(policy.eligible_reader_ids(db, space) - {person.id})
        result.blockers += [
            issue
            for issue in guards.steward_gap(
                space, request.acknowledge_no_steward, remaining=set(), has_members=others
            )
            if isinstance(issue, Blocker)
        ]
        if space.kind == "org" and request.acknowledge_no_steward:
            message = f"{space.name} will have no active steward until one is appointed."
            result.warnings.append(Warning("unit_without_steward", message, str(workspace_id)))
    for workspace_id in set(chosen) - handled - set(grants):
        message = "A successor was chosen for a workspace that does not need one."
        result.blockers.append(Blocker("successor_not_needed", message, str(workspace_id)))


def draft(db: Session, request: Retire, settings: Settings, actor_id: uuid.UUID) -> Draft:
    person = load_person(db, request.person_id)
    result = Draft(person)
    if person.status in DEPARTED:
        result.blockers.append(Blocker("already_departed", "This person has already retired or left."))
    result.blockers += guards.last_administrator(db, person) + guards.not_self(person, actor_id)
    for item in request.successors:
        if item.successor_id == person.id:
            message = "A person who is leaving cannot be their own successor."
            result.blockers.append(Blocker("invalid_successor", message, str(item.workspace_id)))
    grants = policy.direct_grants(db, person.id)
    held = {row.workspace_id for row in positions.current(db, user_id=person.id)}
    successor_ids = {item.workspace_id for item in request.successors}
    readable = set(policy.readable_from_grants(db, grants))
    spaces = named(db, set(grants) | held | readable | successor_ids | set(request.keep_workspace_ids))
    for workspace_id in request.keep_workspace_ids:
        if workspace_id not in grants:
            message = "Only the person's own memberships can be kept."
            result.blockers.append(Blocker("not_a_member", message, str(workspace_id)))
    handled = _positions(db, result, request, spaces, settings)
    _last_stewards(db, result, request, spaces, grants, handled)
    for workspace_id in sorted(grants, key=lambda key: spaces[key].name):
        if workspace_id not in request.keep_workspace_ids:
            result.actions.append(set_role(person, spaces[workspace_id], grants[workspace_id], None))
    result.actions.append(set_status(person, request.status, today(settings)))
    why = "Its stewards will be asked to reassign them."
    result.warnings += task_warnings(db, person, {key: spaces[key] for key in readable}, why)
    return result


def build(db: Session, request: Retire, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Positions and successors, memberships removed, status, and open-task counts per workspace."""
    return draft(db, request, settings, actor_id).plan(
        request.kind, actor_id, request.model_dump(mode="json")
    )


def apply(
    db: Session, actor: User, plan: Plan, request: Retire, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings, actor.id)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {"stewards_notified": notify_stewards(db, result.person, plan, "departure")}
