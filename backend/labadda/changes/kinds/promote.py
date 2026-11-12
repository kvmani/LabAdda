"""PO-13: change designation and optionally the role (or a vacant position) in one workspace."""

import uuid

from sqlalchemy.orm import Session

from ... import policy, positions
from ...config import Settings
from ...models import User, Workspace
from .. import guards
from ..actions import Action, Appointment, Draft, appoint, set_role
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import Promote
from .common import load_person, load_space, lock_person_scope, today

ACTIVE_STATUSES = {"invited", "active", "on_leave"}


def lock_scope(db: Session, request: Promote) -> None:
    lock_person_scope(db, request.person_id, {request.workspace_id} if request.workspace_id else set())


def _designation(person: User, value: str | None) -> Action:
    def run(db: Session, actor: User, reason: str) -> None:
        person.designation = value

    return Action(
        Step(
            "identity",
            str(person.id),
            f"Change the designation of {person.display_name} to {value or 'none'}",
            Snapshot({"designation": person.designation}),
            Snapshot({"designation": value}),
        ),
        run,
    )


def _role_change(db: Session, draft: Draft, request: Promote, space: Workspace) -> None:
    person = draft.person
    before = policy.direct_grants(db, person.id).get(space.id)
    if before is None:
        message = f"{person.display_name} is not a member of {space.name}. Use Additional charge instead."
        draft.blockers.append(Blocker("not_a_member", message, str(space.id)))
        return
    if before == request.role:
        return
    draft.actions.append(set_role(person, space, before, request.role))
    name = person.display_name
    if request.role == "steward":
        message = f"{name} will be able to moderate {space.name} and manage its members."
        draft.warnings.append(Warning("moderation_gained", message, str(space.id)))
        return
    draft.warnings.append(
        Warning("moderation_lost", f"{name} will no longer moderate {space.name}.", str(space.id))
    )
    if any(
        row.position != "charge" for row in positions.current(db, user_id=person.id, workspace_id=space.id)
    ):
        message = f"{name} holds a position in {space.name}. Use Change of head or deputy first."
        draft.blockers.append(Blocker("holds_position", message, str(space.id)))
    remaining = guards.active_stewards(db, space.id) - {person.id}
    others = bool(policy.eligible_reader_ids(db, space) - {person.id})
    issues = guards.steward_gap(space, False, remaining=remaining, has_members=others)
    draft.blockers += [issue for issue in issues if isinstance(issue, Blocker)]


def _position(db: Session, draft: Draft, request: Promote, space: Workspace, settings: Settings) -> None:
    if request.position is None:
        return
    draft.blockers += guards.position_holder(db, draft.person, space)
    if request.position == "head" and positions.current_head(db, space.id, acting=False) is not None:
        message = f"{space.name} already has a Head. Use Change of head to replace them."
        draft.blockers.append(Blocker("unit_has_head", message, str(space.id)))
    held = positions.current(db, user_id=draft.person.id, workspace_id=space.id)
    if any(row.position == request.position for row in held):
        message = f"{draft.person.display_name} already holds this position."
        draft.blockers.append(Blocker("already_holds", message, str(space.id)))
    item = Appointment(request.position, today(settings))
    draft.actions.append(appoint(draft.person, space, item))


def draft(db: Session, request: Promote, settings: Settings) -> Draft:
    result = Draft(load_person(db, request.person_id), affected_people=0)
    if result.person.status not in ACTIVE_STATUSES:
        result.blockers.append(
            Blocker("person_inactive", "Only invited, active or on-leave people can be promoted.")
        )
    if "designation" in request.model_fields_set and request.designation != result.person.designation:
        result.actions.append(_designation(result.person, request.designation))
    if request.workspace_id is not None:
        space = load_space(db, request.workspace_id)
        _role_change(db, result, request, space)
        _position(db, result, request, space, settings)
    if not result.actions and not result.blockers:
        result.blockers.append(Blocker("no_changes", "These values already match the person's record."))
    if any(
        action.step.target_type == "workspace" or "position" in action.step.after.to_dict()
        for action in result.actions
    ):
        result.affected_people = 1
    return result


def build(db: Session, request: Promote, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """The designation, role and position steps, and whether moderation powers change."""
    return draft(db, request, settings).plan(
        request.kind, actor_id, request.model_dump(mode="json", exclude_unset=True)
    )


def apply(
    db: Session, actor: User, plan: Plan, request: Promote, settings: Settings, reason: str
) -> tuple[User, dict]:
    result = draft(db, request, settings)
    result.run(db, actor, reason)
    result.person.revision += 1
    db.flush()
    return result.person, {}
