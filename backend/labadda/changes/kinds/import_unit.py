"""Spreadsheet import: create one missing unit through the ordinary unit-creation steps."""

import uuid

from sqlalchemy.orm import Session

from ...config import Settings
from ...errors import Invalid
from ...models import User, Workspace
from .. import import_tree
from ..import_requests import ImportUnit
from ..plan import Plan, Snapshot
from ..unit_requests import UnitCreate
from . import unit_common as units
from . import unit_create


def lock_scope(db: Session, request: ImportUnit) -> None:
    """Every import step shares the top unit's lock, so two imports run one after the other."""
    units.lock_units(db, {import_tree.organisation_root(db).id})


def _create(parent: Workspace, request: ImportUnit) -> UnitCreate:
    node = request.path[-1]
    return UnitCreate(
        kind="unit_create",
        parent_id=parent.id,
        name=node.name,
        code=node.code,
        level=node.level,
    )


def build(db: Session, request: ImportUnit, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """A unit whose parent is made earlier in the same import is described from the names alone."""
    found = import_tree.find(db, request.path)
    snapshot = request.model_dump(mode="json")
    if found.blockers:
        return Plan(
            "unit_create", str(actor_id), Snapshot(snapshot), Snapshot({}), blockers=tuple(found.blockers)
        )
    parent = found.units[-2] if len(request.path) > 1 else import_tree.organisation_root(db)
    node = request.path[-1]
    if found.units[-1] is not None:
        return Plan("unit_create", str(actor_id), Snapshot(snapshot), Snapshot({}))
    if parent is None:
        parent = Workspace(kind="org", name=request.path[-2].name)
        box: dict = {}
        action = units.create_action(node.name, node.code, parent, box, node.level)
        blockers = tuple(units.code_taken(db, node.code))
        return Plan(
            "unit_create",
            str(actor_id),
            Snapshot(snapshot),
            Snapshot({}),
            steps=(action.step,),
            blockers=blockers,
        )
    draft = unit_create._draft(db, _create(parent, request), settings)
    draft.warnings = []
    return draft.plan("unit_create", actor_id, snapshot)


def apply(db: Session, actor: User, plan: Plan, request: ImportUnit, settings: Settings, reason: str):
    found = import_tree.find(db, request.path)
    if found.blockers:
        raise Invalid("plan_blocked", "Resolve the blocking problems before applying this change.")
    if found.units[-1] is not None:
        return found.units[-1], {}
    parent = found.units[-2] if len(request.path) > 1 else import_tree.organisation_root(db)
    if parent is None:
        raise Invalid("plan_blocked", "A unit above this one is missing.")
    create = _create(parent, request)
    return unit_create.apply(db, actor, plan, create, settings, reason)
