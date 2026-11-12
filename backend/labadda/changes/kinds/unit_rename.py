"""PO-19: rename and/or recode a unit; identifiers do not change, so links keep working."""

import uuid

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import User
from ..actions import Action
from ..plan import Blocker, Plan, Snapshot, Step
from ..requests import UnitRename
from . import unit_common as units
from .common import load_space


def lock_scope(db: Session, request: UnitRename) -> None:
    units.lock_units(db, {request.unit_id})


def _draft(db: Session, request: UnitRename, settings: Settings) -> units.UnitDraft:
    unit = load_space(db, request.unit_id)
    draft = units.UnitDraft(unit)
    draft.blockers += units.org_unit(unit)
    name = request.name if request.name is not None else unit.name
    code = request.code if request.code is not None else unit.code
    if (name, code) == (unit.name, unit.code):
        draft.blockers.append(Blocker("no_change", "The name and code are already these."))
    if code != unit.code and code is not None:
        draft.blockers += units.code_taken(db, code, unit.id)
    parts = []
    if name != unit.name:
        parts.append(f"Rename {unit.name} to {name}")
    if code != unit.code:
        parts.append(f"set the code of {name} to {code}")
    summary = " and ".join(parts)
    before = {"name": unit.name, "code": unit.code}

    def run(db: Session, actor: User, reason: str) -> None:
        unit.name = name
        unit.code = code

    step = Step("workspace", str(unit.id), summary, Snapshot(before), Snapshot({"name": name, "code": code}))
    draft.actions.append(Action(step, run))
    return draft


def build(db: Session, request: UnitRename, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitRename, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.unit, {}
