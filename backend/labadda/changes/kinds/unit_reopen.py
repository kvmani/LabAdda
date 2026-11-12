"""PO-19: reopen a closed unit under an open parent."""

import uuid

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import User, Workspace
from ..plan import Blocker, Plan
from ..requests import UnitReopen
from . import unit_common as units
from .common import load_space
from .unit_close import archive_action, lock_scope  # noqa: F401  (the service calls lock_scope here)


def _draft(db: Session, request: UnitReopen, settings: Settings) -> units.UnitDraft:
    unit = load_space(db, request.unit_id)
    parent = db.get(Workspace, unit.parent_id) if unit.parent_id else None
    draft = units.UnitDraft(unit)
    draft.blockers += units.org_unit(unit)
    if not unit.archived:
        draft.blockers.append(Blocker("no_change", f"{unit.name} is already open."))
    if parent is not None and parent.archived:
        message = f"{parent.name} is closed. Reopen it or move {unit.name} first."
        draft.blockers.append(Blocker("parent_closed", message, str(parent.id)))
    draft.actions.append(archive_action(unit, parent, False))
    return draft


def build(db: Session, request: UnitReopen, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitReopen, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.unit, {}
