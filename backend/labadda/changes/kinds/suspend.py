"""PO-18: stop a person's access immediately; memberships are kept but give no access."""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import User
from .. import guards
from ..actions import Draft, end_position, set_status
from ..plan import Blocker, Plan, Warning
from ..requests import Suspend
from .common import load_person, lock_person_scope, named, today

SUSPENDABLE = {"invited", "active", "on_leave"}


def lock_scope(db: Session, request: Suspend) -> None:
    lock_person_scope(db, request.person_id)


def draft(db: Session, request: Suspend, settings: Settings, actor_id: uuid.UUID) -> Draft:
    person = load_person(db, request.person_id)
    result = Draft(person)
    if person.status not in SUSPENDABLE:
        result.blockers.append(Blocker("person_unavailable", "This person is already without access."))
    result.blockers += guards.last_administrator(db, person) + guards.not_self(person, actor_id)
    grants = policy.direct_grants(db, person.id)
    held = positions.current(db, user_id=person.id)
    spaces = named(db, set(grants) | {row.workspace_id for row in held})
    for row in held:
        result.actions.append(end_position(person, row, spaces[row.workspace_id]))
    result.actions.append(set_status(person, "suspended", today(settings)))
    for workspace_id in sorted(grants, key=lambda key: spaces[key].name):
        if grants[workspace_id] == "steward" and not guards.active_stewards(db, workspace_id) - {person.id}:
            message = f"{spaces[workspace_id].name} will have no active steward. Appoint one soon."
            result.warnings.append(Warning("no_active_steward", message, str(workspace_id)))
    return result


def build(db: Session, request: Suspend, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Positions ended, status suspended, sign-in and sessions ended at once."""
    return draft(db, request, settings, actor_id).plan(
        request.kind, actor_id, request.model_dump(mode="json")
    )


def apply(
    db: Session, actor: User, plan: Plan, request: Suspend, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings, actor.id)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
