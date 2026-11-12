"""Build and execute staff-only edits without touching identity or workspace authority."""

import uuid

from sqlalchemy.orm import Session

from ...config import Settings
from ...errors import NotFound
from ...models import User
from ..guards import unique_employee_number
from ..plan import Blocker, Plan, Snapshot, Step
from ..requests import EditPerson


def build(db: Session, request: EditPerson, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Read current staff values and expose exact before/after metadata only."""
    person = db.get(User, request.person_id, populate_existing=True)
    if person is None:
        raise NotFound()
    selected = request.fields.model_dump(exclude_unset=True)
    changed = {name: value for name, value in selected.items() if value != getattr(person, name)}
    blockers = unique_employee_number(db, changed.get("employee_no"), person.id)
    steps = []
    if changed:
        steps.append(
            Step(
                "identity",
                str(person.id),
                f"Update the staff record for {person.display_name}",
                Snapshot({name: getattr(person, name) for name in changed}),
                Snapshot(changed),
            )
        )
    else:
        blockers.append(Blocker("no_changes", "These values already match the staff record."))
    return Plan(
        kind=request.kind,
        actor_id=str(actor_id),
        request=Snapshot(request.model_dump(mode="json", exclude_unset=True)),
        revisions=Snapshot({str(person.id): person.revision}),
        steps=tuple(steps),
        blockers=tuple(blockers),
    )


def apply(
    db: Session, actor: User, plan: Plan, request: EditPerson, settings: Settings, reason: str
) -> tuple[User, dict]:
    """Apply only rebuilt, whitelisted staff fields inside the caller's transaction."""
    person_id = uuid.UUID(plan.steps[0].target_id)
    person = db.get(User, person_id)
    if person is None:
        raise NotFound()
    for name, value in plan.steps[0].after.to_dict().items():
        setattr(person, name, value)
    person.revision += 1
    db.flush()
    return person, {}
