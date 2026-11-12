"""PO-19: move a unit with its sub-units; the review counts who gains and loses ancestor reads."""

import uuid

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import User
from ..actions import Action
from ..plan import Blocker, Plan, Snapshot, Step
from ..requests import UnitMove
from . import unit_common as units
from .common import load_space


def lock_scope(db: Session, request: UnitMove) -> None:
    unit = load_space(db, request.unit_id)
    units.lock_units(
        db, {request.unit_id, request.new_parent_id, *([unit.parent_id] if unit.parent_id else [])}
    )


def _draft(db: Session, request: UnitMove, settings: Settings) -> units.UnitDraft:
    unit = load_space(db, request.unit_id)
    target = load_space(db, request.new_parent_id)
    old_parent = load_space(db, unit.parent_id) if unit.parent_id else None
    draft = units.UnitDraft(unit)
    draft.blockers += (
        units.org_unit(unit) + units.root_fixed(unit, "moved") + units.open_unit(target, "parent unit")
    )
    parents = units.org_parents(db)
    scope = units.branch(parents, unit.id)
    if target.id in scope:
        message = "A unit cannot move beneath itself or its own sub-units."
        draft.blockers.append(Blocker("cycle", message, str(target.id)))
    if unit.parent_id == target.id:
        draft.blockers.append(Blocker("same_parent", f"{unit.name} is already under {target.name}."))
    if draft.blockers:
        return draft
    after = {**parents, unit.id: target.id}
    draft.warnings += units.access_counts(db, scope, after)
    draft.affected_people = max([warning.count or 0 for warning in draft.warnings], default=0)

    def run(db: Session, actor: User, reason: str) -> None:
        unit.parent_id = target.id

    before = units.unit_state(unit, old_parent)
    after_state = {**before, "parent": target.name, "parent_id": str(target.id)}
    summary = f"Move {unit.name} with its sub-units under {target.name}"
    draft.actions.append(
        Action(Step("workspace", str(unit.id), summary, Snapshot(before), Snapshot(after_state)), run)
    )
    return draft


def build(db: Session, request: UnitMove, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitMove, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.unit, {}
