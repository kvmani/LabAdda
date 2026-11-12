"""Loading, locking, dates and steward notices shared by the P3 change kinds."""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ... import memberships, notify, people, policy
from ...config import Settings
from ...errors import NotFound
from ...models import Membership, TodoList, TodoTask, UnitPosition, User, Workspace
from ..plan import Blocker, Plan, Warning

# Long enough for any acting term or leave; a typing error such as year 2206 is refused.
MAX_TERM = timedelta(days=5 * 366)


def load_person(db: Session, person_id: uuid.UUID) -> User:
    person = db.get(User, person_id, populate_existing=True)
    if person is None:
        raise NotFound()
    return person


def load_space(db: Session, workspace_id: uuid.UUID) -> Workspace:
    space = db.get(Workspace, workspace_id, populate_existing=True)
    if space is None:
        raise NotFound()
    return space


def today(settings: Settings) -> date:
    return people.site_date(settings)


def future_date(value: date | None, settings: Settings, what: str) -> list[Blocker]:
    """Dated changes run forward only: tomorrow or later, within five years."""
    if value is None:
        return []
    start = today(settings)
    if start < value <= start + MAX_TERM:
        return []
    return [Blocker("invalid_date", f"Choose {what} after today and within five years.")]


def lock_person_scope(db: Session, person_id: uuid.UUID, extra: set[uuid.UUID] = frozenset()) -> None:
    """Role locks for every workspace the person belongs to or holds a position in, sorted."""
    scope = set(extra) | set(policy.direct_grants(db, person_id))
    scope |= set(
        db.scalars(
            select(UnitPosition.workspace_id).where(
                UnitPosition.user_id == person_id, UnitPosition.ended_at.is_(None)
            )
        )
    )
    for workspace_id in sorted(scope, key=str):
        memberships.lock_workspace_roles(db, workspace_id)


def named(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, Workspace]:
    if not ids:
        return {}
    return {row.id: row for row in db.scalars(select(Workspace).where(Workspace.id.in_(ids)))}


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


def task_warnings(db: Session, person: User, lost: dict[uuid.UUID, Workspace], why: str) -> list[Warning]:
    """One count per workspace whose stewards will be asked to reassign; never task text."""
    counts = open_task_counts(db, person.id, set(lost))
    warnings = []
    for workspace_id in sorted(counts, key=lambda key: lost[key].name):
        message = (
            f"{counts[workspace_id]} open shared tasks are assigned to {person.display_name} in "
            f"{lost[workspace_id].name}. {why}"
        )
        warnings.append(Warning("open_tasks", message, str(workspace_id), counts[workspace_id]))
    return warnings


def notify_stewards(db: Session, person: User, plan: Plan, source_type: str) -> int:
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
            source_type=source_type,
            source_id=person.id,
            occurrence=plan.digest[:32],
        )
    return notified
