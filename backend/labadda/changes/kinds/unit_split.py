"""PO-19: split a new sibling unit from a unit and move the chosen people into it in one plan."""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import User, Workspace
from .. import guards
from ..actions import end_position, set_role
from ..plan import Blocker, Plan, Warning
from ..requests import UnitSplit
from . import unit_common as units
from .common import load_person, load_space, open_task_counts


def lock_scope(db: Session, request: UnitSplit) -> None:
    source = load_space(db, request.unit_id)
    units.lock_units(db, {source.id, *([source.parent_id] if source.parent_id else [])})
    for person_id in request.person_ids:
        db.get(User, person_id, with_for_update=True, populate_existing=True)


def _person_blockers(person: User, source: Workspace) -> list[Blocker]:
    if person.home_workspace_id == source.id and person.status in units.MOVABLE:
        return []
    message = f"{person.display_name} must have {source.name} as their home unit to move with it."
    return [Blocker("person_not_in_unit", message, str(person.id))]


def _move_person(db: Session, person: User, source: Workspace, name: str, box: dict, draft) -> str:
    role = policy.direct_grants(db, person.id).get(source.id) or "member"
    for row in positions.current(db, user_id=person.id, workspace_id=source.id):
        draft.actions.append(end_position(person, row, source))
    draft.actions.append(units.join_new_action(person, name, role, box))
    draft.actions.append(set_role(person, source, role, None))
    draft.actions.append(units.home_in_new_action(person, source, name, box))
    return role


def _steward_gaps(db: Session, request: UnitSplit, source: Workspace, moved: dict[uuid.UUID, str]):
    moving_out = {person for person, role in moved.items() if role == "steward"}
    remaining = guards.active_stewards(db, source.id) - moving_out
    others = policy.eligible_reader_ids(db, source) - set(moved)
    gaps = guards.steward_gap(
        source, request.acknowledge_no_steward, remaining=remaining, has_members=bool(others)
    )
    new_stewards = {person for person in moving_out if (u := db.get(User, person)) and u.is_active}
    stub = Workspace(kind="org", name=request.name)
    return gaps + guards.steward_gap(
        stub, request.acknowledge_no_steward, remaining=new_stewards, has_members=True
    )


def _draft(db: Session, request: UnitSplit, settings: Settings) -> units.UnitDraft:
    source = load_space(db, request.unit_id)
    draft = units.UnitDraft(source)
    draft.blockers += units.org_unit(source) + units.root_fixed(source, "split") + units.open_unit(source)
    draft.blockers += units.code_taken(db, request.code)
    if draft.blockers or source.parent_id is None:
        return draft
    parent = load_space(db, source.parent_id)
    box = draft.box
    draft.actions.append(units.create_action(request.name, request.code, parent, box))
    moved: dict[uuid.UUID, str] = {}
    open_tasks = 0
    for person_id in request.person_ids:
        person = load_person(db, person_id)
        draft.blockers += _person_blockers(person, source)
        moved[person.id] = _move_person(db, person, source, request.name, box, draft)
        open_tasks += sum(open_task_counts(db, person.id, {source.id}).values())
    issues = _steward_gaps(db, request, source, moved)
    draft.blockers += [issue for issue in issues if isinstance(issue, Blocker)]
    draft.warnings += [issue for issue in issues if isinstance(issue, Warning)]
    draft.affected_people = len(moved)
    if moved:
        noun = "person" if len(moved) == 1 else "people"
        message = f"{len(moved)} {noun} will no longer be able to read {source.name}."
        draft.warnings.append(Warning("access_lost", message, str(source.id), len(moved)))
    if open_tasks:
        message = (
            f"{open_tasks} open shared tasks assigned to these people stay in {source.name}. "
            "Its stewards should reassign them."
        )
        draft.warnings.append(Warning("open_tasks", message, str(source.id), open_tasks))
    return draft


def build(db: Session, request: UnitSplit, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitSplit, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.box["unit"], {}
