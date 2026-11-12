"""PO-19: merge unit A into B. People of A get B as home; A is closed and stays readable history."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import positions
from ...config import Settings
from ...models import Membership, User, Workspace
from ..actions import Action, end_position, set_role
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import UnitMerge
from . import unit_common as units
from .common import load_person, load_space
from .unit_close import archive_action


def lock_scope(db: Session, request: UnitMerge) -> None:
    units.lock_units(db, {request.unit_id, request.into_unit_id})
    units.people_with_home(db, request.unit_id, for_update=True)


def _blockers(db: Session, source: Workspace, target: Workspace, parents: dict) -> list[Blocker]:
    blockers = units.org_unit(source) + units.root_fixed(source, "merged")
    blockers += units.open_unit(source, "unit to merge") + units.open_unit(target, "unit to merge into")
    if source.id == target.id:
        blockers.append(Blocker("same_unit", "Choose two different units."))
    elif target.id in units.branch(parents, source.id):
        message = f"{target.name} is inside {source.name}. Move it out before merging."
        blockers.append(Blocker("cycle", message, str(target.id)))
    return blockers


def _reparent(child: Workspace, source: Workspace, target: Workspace) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        child.parent_id = target.id

    before = units.unit_state(child, source)
    after = {**before, "parent": target.name, "parent_id": str(target.id)}
    summary = f"Move {child.name} from under {source.name} to under {target.name}"
    return Action(Step("workspace", str(child.id), summary, Snapshot(before), Snapshot(after)), run)


def _people(db: Session, source: Workspace, target: Workspace, draft: units.UnitDraft) -> dict:
    rows = db.execute(select(Membership.user_id).where(Membership.workspace_id == target.id))
    held = set(rows.scalars())
    moved = units.people_with_home(db, source.id)
    if len(moved) > units.MAX_MOVED_PEOPLE:
        message = f"{len(moved)} people belong to {source.name}. Transfer some of them first."
        draft.blockers.append(Blocker("too_many_people", message, str(source.id), len(moved)))
        return {}
    added: dict[uuid.UUID, set[uuid.UUID]] = {}
    for person in moved:
        draft.actions.append(units.set_home(person, target.id, units.home_step(person, source, target)))
        if person.id not in held:
            draft.actions.append(set_role(person, target, None, "member"))
            added[person.id] = {target.id}
    return added


def _draft(db: Session, request: UnitMerge, settings: Settings) -> units.UnitDraft:
    source = load_space(db, request.unit_id)
    target = load_space(db, request.into_unit_id)
    parents = units.org_parents(db)
    draft = units.UnitDraft(source)
    draft.blockers += _blockers(db, source, target, parents)
    if draft.blockers:
        return draft
    children = list(
        db.scalars(select(Workspace).where(Workspace.parent_id == source.id, Workspace.kind == "org"))
    )
    draft.actions += [_reparent(child, source, target) for child in sorted(children, key=lambda c: c.name)]
    added = _people(db, source, target, draft)
    ended = positions.current(db, workspace_id=source.id)
    draft.actions += [end_position(load_person(db, row.user_id), row, source) for row in ended]
    parent = db.get(Workspace, source.parent_id)
    draft.actions.append(archive_action(source, parent, True))
    after = {**parents, **{child.id: target.id for child in children}}
    draft.warnings += units.access_counts(db, units.branch(parents, source.id), after, added)
    draft.affected_people = units.person_count(db, source.id)
    members = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.workspace_id == source.id)
    )
    if members:
        message = f"{members} members keep read access to the history of {source.name}."
        draft.warnings.append(Warning("history_kept", message, str(source.id), members))
    return draft


def build(db: Session, request: UnitMerge, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitMerge, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.unit, {}
