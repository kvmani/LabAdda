"""Move a person's home unit with reviewed access, steward and open-assignment consequences."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import memberships, notify, policy
from ...config import Settings
from ...errors import NotFound
from ...models import Membership, TodoList, TodoTask, User, Workspace
from ..plan import Blocker, Plan, Snapshot, Step, Warning
from ..requests import Transfer

MOVABLE_STATUSES = {"invited", "active", "on_leave"}


@dataclass(frozen=True)
class Proposal:
    """Current and proposed direct grants; access is derived from these by ``policy``."""

    person: User
    source: Workspace | None
    target: Workspace
    before: dict[uuid.UUID, str]
    after: dict[uuid.UUID, str]
    names: dict[uuid.UUID, Workspace]


def lock_scope(db: Session, request: Transfer) -> None:
    """Take workspace role locks before the person row, matching membership writers' order."""
    home = db.scalar(select(User.home_workspace_id).where(User.id == request.person_id))
    scope = {request.to_unit_id, *request.leave_workspace_ids}
    if home is not None:
        scope.add(home)
    for workspace_id in sorted(scope, key=str):
        memberships.lock_workspace_roles(db, workspace_id)


def _propose(db: Session, request: Transfer) -> Proposal:
    person = db.get(User, request.person_id, populate_existing=True)
    target = db.get(Workspace, request.to_unit_id, populate_existing=True)
    if person is None or target is None:
        raise NotFound()
    source = db.get(Workspace, person.home_workspace_id) if person.home_workspace_id else None
    before = policy.direct_grants(db, person.id)
    after = dict(before)
    if source is not None and not request.keep_previous:
        after.pop(source.id, None)
    for workspace_id in request.leave_workspace_ids:
        after.pop(workspace_id, None)
    after[target.id] = request.role
    readable = set(policy.readable_from_grants(db, before)) | set(policy.readable_from_grants(db, after))
    rows = db.scalars(select(Workspace).where(Workspace.id.in_(readable | set(request.leave_workspace_ids))))
    return Proposal(person, source, target, before, after, {row.id: row for row in rows})


def _blockers(db: Session, request: Transfer, proposal: Proposal) -> list[Blocker]:
    blockers = []
    if proposal.person.status not in MOVABLE_STATUSES:
        blockers.append(Blocker("person_inactive", "Only invited, active or on-leave people can transfer."))
    target = proposal.target
    if target.kind != "org" or target.archived:
        blockers.append(Blocker("unit_unavailable", "Choose an open unit of the organisation."))
    if proposal.source is not None and proposal.source.id == target.id:
        blockers.append(Blocker("same_unit", "The person already has this home unit."))
    for workspace_id in request.leave_workspace_ids:
        space = proposal.names.get(workspace_id)
        if space is None or space.kind == "org" or workspace_id not in proposal.before:
            blockers.append(
                Blocker("not_a_member", "Only their own projects and groups can be left.", str(workspace_id))
            )
        elif _leaves_without_steward(db, proposal, workspace_id) and _other_members(db, proposal, space):
            message = f"{space.name} would have no steward. Keep this membership or name a successor first."
            blockers.append(Blocker("group_needs_steward", message, str(workspace_id)))
    return blockers


def _leaves_without_steward(db: Session, proposal: Proposal, workspace_id: uuid.UUID) -> bool:
    person = proposal.person
    stewarding = proposal.before.get(workspace_id) == "steward" and person.is_active
    return (
        stewarding
        and proposal.after.get(workspace_id) != "steward"
        and (memberships.active_steward_count(db, workspace_id) <= 1)
    )


def _other_members(db: Session, proposal: Proposal, space: Workspace) -> bool:
    return bool(policy.eligible_reader_ids(db, space) - {proposal.person.id})


def _steward_issue(db: Session, request: Transfer, proposal: Proposal) -> list[Blocker | Warning]:
    """PO-08: leaving a unit without a steward needs an explicit acknowledgement."""
    source = proposal.source
    if source is None or not _leaves_without_steward(db, proposal, source.id):
        return []
    if request.acknowledge_no_steward:
        message = f"{source.name} will have no active steward until one is appointed."
        return [Warning("unit_without_steward", message, str(source.id))]
    message = f"{source.name} would have no active steward. Tick the acknowledgement to continue."
    return [Blocker("unit_without_steward", message, str(source.id))]


def open_task_counts(db: Session, person_id: uuid.UUID, workspaces: set[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Count open shared tasks assigned to the person; titles and descriptions are never read."""
    if not workspaces:
        return {}
    rows = db.execute(
        select(TodoList.workspace_id, func.count())
        .join(TodoTask, TodoTask.list_id == TodoList.id)
        .where(
            TodoList.workspace_id.in_(workspaces),
            TodoTask.assignee_id == person_id,
            TodoTask.done.is_(False),
        )
        .group_by(TodoList.workspace_id)
    ).all()
    return {workspace_id: count for workspace_id, count in rows if count}


def _access_warnings(db: Session, proposal: Proposal) -> list[Warning]:
    before = set(policy.readable_from_grants(db, proposal.before))
    after = set(policy.readable_from_grants(db, proposal.after))
    name = proposal.person.display_name
    warnings = [
        Warning("access_gained", f"{name} will be able to read {proposal.names[ws].name}.", str(ws))
        for ws in sorted(after - before, key=lambda ws: proposal.names[ws].name)
    ]
    lost = sorted(before - after, key=lambda ws: proposal.names[ws].name)
    warnings += [
        Warning("access_lost", f"{name} will no longer be able to read {proposal.names[ws].name}.", str(ws))
        for ws in lost
    ]
    counts = open_task_counts(db, proposal.person.id, set(lost))
    for workspace_id in lost:
        if workspace_id in counts:
            message = (
                f"{counts[workspace_id]} open shared tasks are assigned to {name} in "
                f"{proposal.names[workspace_id].name}. Its stewards will be asked to reassign them."
            )
            warnings.append(Warning("open_tasks", message, str(workspace_id), counts[workspace_id]))
    return warnings


def _membership_step(proposal: Proposal, workspace_id: uuid.UUID) -> Step:
    space = proposal.names.get(workspace_id) or proposal.target
    name = proposal.person.display_name
    role = proposal.after.get(workspace_id)
    summary = f"Remove {name} from {space.name}" if role is None else f"Add {name} to {space.name} as {role}"
    if role is not None and workspace_id in proposal.before:
        summary = f"Set the role of {name} in {space.name} to {role}"
    return Step(
        "workspace",
        str(workspace_id),
        summary,
        Snapshot({"role": proposal.before.get(workspace_id)}),
        Snapshot({"role": role}),
    )


def _steps(proposal: Proposal) -> tuple[Step, ...]:
    person, source, target = proposal.person, proposal.source, proposal.target
    home = Step(
        "identity",
        str(person.id),
        f"Change the home unit of {person.display_name} to {target.name}",
        Snapshot({"home_unit_id": str(source.id) if source else None, "home_unit": source and source.name}),
        Snapshot({"home_unit_id": str(target.id), "home_unit": target.name}),
    )
    changed = [
        workspace_id
        for workspace_id in sorted(set(proposal.before) | set(proposal.after), key=str)
        if proposal.before.get(workspace_id) != proposal.after.get(workspace_id)
    ]
    ordered = sorted(changed, key=lambda workspace_id: workspace_id != target.id)
    return (home, *(_membership_step(proposal, workspace_id) for workspace_id in ordered))


def build(db: Session, request: Transfer, actor_id: uuid.UUID, settings: Settings) -> Plan:
    """Compute memberships, access gained/lost and open-assignment counts without writing."""
    proposal = _propose(db, request)
    issues = _steward_issue(db, request, proposal)
    warnings = [issue for issue in issues if isinstance(issue, Warning)]
    blockers = _blockers(db, request, proposal) + [issue for issue in issues if isinstance(issue, Blocker)]
    warnings += _access_warnings(db, proposal)
    steps = _steps(proposal)
    access_changes = any(warning.code.startswith("access_") for warning in warnings)
    return Plan(
        kind=request.kind,
        actor_id=str(actor_id),
        request=Snapshot(request.model_dump(mode="json")),
        revisions=Snapshot({str(proposal.person.id): proposal.person.revision}),
        steps=steps,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        affected_people=1 if access_changes or len(steps) > 1 else 0,
    )


def _notify_stewards(db: Session, person: User, plan: Plan) -> int:
    """Tell each affected workspace's stewards to reassign; the notice names only person and count."""
    notified = 0
    for warning in plan.warnings:
        if warning.code != "open_tasks" or warning.target_id is None:
            continue
        workspace_id = uuid.UUID(warning.target_id)
        stewards = db.scalars(
            select(Membership.user_id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == workspace_id,
                Membership.role == "steward",
                User.is_active.is_(True),
                User.id != person.id,
            )
        ).all()
        notified += notify.create(
            db,
            recipients=stewards,
            kind="reassign",
            workspace_id=workspace_id,
            source_type="transfer",
            source_id=person.id,
            occurrence=plan.digest[:32],
        )
    return notified


def apply(
    db: Session, actor: User, plan: Plan, request: Transfer, settings: Settings, reason: str
) -> tuple[User, dict]:
    """Write the reviewed home unit and memberships, then queue steward notices in this transaction."""
    person = db.get(User, request.person_id)
    if person is None:
        raise NotFound()
    person.home_workspace_id = request.to_unit_id
    person.revision += 1
    for step in plan.steps[1:]:
        workspace_id = uuid.UUID(step.target_id)
        role = step.after.to_dict()["role"]
        if role is None:
            memberships.remove_membership(
                db, actor=actor, workspace_id=workspace_id, user_id=person.id, reason=reason
            )
        else:
            memberships.set_membership(
                db, actor=actor, workspace_id=workspace_id, user_id=person.id, role=str(role), reason=reason
            )
    db.flush()
    return person, {"stewards_notified": _notify_stewards(db, person, plan)}
