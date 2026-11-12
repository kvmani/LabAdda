"""PO-19: close (archive) a unit that has no people and no open sub-units; nothing is deleted."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import positions
from ...config import Settings
from ...models import Membership, User, Workspace
from ..actions import Action, end_position
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import UnitClose, UnitReopen
from . import unit_common as units
from .common import load_person, load_space


def lock_scope(db: Session, request: UnitClose | UnitReopen) -> None:
    unit = load_space(db, request.unit_id)
    units.lock_units(db, {unit.id, *([unit.parent_id] if unit.parent_id else [])})


def archive_action(unit: Workspace, parent: Workspace | None, archived: bool) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        unit.archived = archived

    before = units.unit_state(unit, parent)
    verb = "Close" if archived else "Reopen"
    summary = f"{verb} {unit.name}" + (" and keep it readable as history" if archived else "")
    return Action(
        Step(
            "workspace", str(unit.id), summary, Snapshot(before), Snapshot({**before, "archived": archived})
        ),
        run,
    )


def _draft(db: Session, request: UnitClose, settings: Settings) -> units.UnitDraft:
    unit = load_space(db, request.unit_id)
    parent = db.get(Workspace, unit.parent_id) if unit.parent_id else None
    draft = units.UnitDraft(unit)
    draft.blockers += units.org_unit(unit) + units.root_fixed(unit, "closed")
    if unit.archived:
        draft.blockers.append(Blocker("no_change", f"{unit.name} is already closed."))
    count = units.person_count(db, unit.id)
    if count:
        message = f"{count} people have {unit.name} as their home unit. Transfer them first."
        draft.blockers.append(Blocker("unit_has_people", message, str(unit.id)))
    open_children = db.scalar(
        select(func.count())
        .select_from(Workspace)
        .where(Workspace.parent_id == unit.id, Workspace.kind == "org", Workspace.archived.is_(False))
    )
    if open_children:
        message = f"{unit.name} has {open_children} open sub-units. Move or close them first."
        draft.blockers.append(Blocker("unit_has_subunits", message, str(unit.id)))
    for row in positions.current(db, workspace_id=unit.id):
        draft.actions.append(end_position(load_person(db, row.user_id), row, unit))
    members = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.workspace_id == unit.id)
    )
    if members:
        message = f"{members} members keep read access to the history of {unit.name}."
        draft.warnings.append(Warning("history_kept", message, str(unit.id), members))
    draft.actions.append(archive_action(unit, parent, True))
    return draft


def build(db: Session, request: UnitClose, actor_id: uuid.UUID, settings: Settings) -> Plan:
    return _draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(db: Session, actor: User, plan: Plan, request: UnitClose, settings: Settings, reason: str):
    draft = _draft(db, request, settings)
    draft.run(db, actor, reason)
    return draft.unit, {}
