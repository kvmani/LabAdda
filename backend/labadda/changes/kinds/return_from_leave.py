"""PO-16: back from leave; acting appointments made for the absence end and their roles revert."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import Settings
from ...models import UnitPosition, User
from ..actions import Draft, end_position, set_status
from ..plan import Blocker, Plan
from ..requests import Return
from .common import load_person, load_space, lock_person_scope, today


def _covering(db: Session, person: User) -> list[UnitPosition]:
    held = select(UnitPosition.id).where(UnitPosition.user_id == person.id, UnitPosition.ended_at.is_(None))
    return list(
        db.scalars(
            select(UnitPosition)
            .where(UnitPosition.covers_id.in_(held), UnitPosition.ended_at.is_(None))
            .order_by(UnitPosition.created_at, UnitPosition.id)
        )
    )


def lock_scope(db: Session, request: Return) -> None:
    person = load_person(db, request.person_id)
    lock_person_scope(db, person.id, {row.workspace_id for row in _covering(db, person)})


def draft(db: Session, request: Return, settings: Settings) -> Draft:
    person = load_person(db, request.person_id)
    result = Draft(person, affected_people=0 if person.is_active else 1)
    if person.status != "on_leave":
        result.blockers.append(Blocker("not_on_leave", "This person is not on leave."))
    result.actions.append(set_status(person, "active", today(settings)))
    for row in _covering(db, person):
        holder = load_person(db, row.user_id)
        result.actions.append(end_position(holder, row, load_space(db, row.workspace_id), revert=True))
        result.affected_people += 1
    return result


def build(db: Session, request: Return, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Active status, and each acting appointment covering this person ended."""
    return draft(db, request, settings).plan(request.kind, actor_id, request.model_dump(mode="json"))


def apply(
    db: Session, actor: User, plan: Plan, request: Return, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
