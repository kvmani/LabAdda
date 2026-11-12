"""PO-19: create an organisation unit under an open parent, optionally with a Head."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import User, Workspace
from .. import guards
from ..actions import Action
from ..plan import Plan, Snapshot, Step, Warning
from ..requests import UnitCreate
from . import unit_common as units
from .common import load_person, load_space, today


def lock_scope(db: Session, request: UnitCreate) -> None:
    units.lock_units(db, {request.parent_id})


def _head(head: User, request: UnitCreate, box: dict, start) -> list[Action]:
    def appoint(db: Session, actor: User, reason: str) -> None:
        positions.appoint(
            db,
            actor=actor,
            workspace_id=box["unit"].id,
            user_id=head.id,
            position="head",
            starts_on=start,
            revert_role="none",
            reason=reason,
        )

    name = head.display_name
    title = Step(
        "identity",
        str(head.id),
        f"Appoint {name} as Head of {request.name}",
        Snapshot({"position": None}),
        Snapshot({"position": "Head", "unit": request.name, "returns_to": "none"}),
    )
    return [units.join_new_action(head, request.name, "steward", box), Action(title, appoint)]


def _draft(db: Session, request: UnitCreate, settings: Settings) -> units.UnitDraft:
    parent = load_space(db, request.parent_id)
    draft = units.UnitDraft(parent)
    draft.blockers += units.open_unit(parent, "parent unit") + units.code_taken(db, request.code)
    box = draft.box
    draft.actions.append(units.create_action(request.name, request.code, parent, box))
    if request.head_id is None:
        message = f"{request.name} will have no Head or steward until one is appointed."
        draft.warnings.append(Warning("unit_without_steward", message))
        return draft
    head = load_person(db, request.head_id)
    stub = Workspace(kind="org", name=request.name, parent_id=parent.id)
    draft.blockers += guards.position_holder(db, head, stub, joining=True)
    draft.actions += _head(head, request, box, today(settings))
    draft.affected_people = 1
    parents = units.org_parents(db)
    gained = [parent.id, *policy.ancestors(parents, parent.id)]
    reads = policy.readable_from_grants(db, policy.direct_grants(db, head.id))
    names = {row.id: row for row in db.scalars(select(Workspace).where(Workspace.id.in_(gained)))}
    for unit_id in sorted(set(gained) - set(reads), key=lambda key: names[key].name):
        message = f"{head.display_name} will be able to read {names[unit_id].name}."
        draft.warnings.append(Warning("access_gained", message, str(unit_id), 1))
    return draft


def build(db: Session, request: UnitCreate, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitCreate, settings: Settings, reason: str):
    """The unit does not exist until here; the draft is rebuilt under lock and run in order."""
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.box["unit"], {}
