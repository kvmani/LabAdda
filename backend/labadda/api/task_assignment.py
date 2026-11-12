"""C2 assignment and current-grant My Tasks; assignment never grants access."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .. import policy, task_events, task_history
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound, Unauthenticated
from ..identity_locks import lock_identity
from ..models import TodoList, TodoTask, User
from ..security import utcnow
from .todos import _actor, _list, _task_json

router = APIRouter(prefix="/todos", tags=["todos"])
State = Literal["todo", "in_progress", "blocked", "done"]


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID | None
    revision: int = Field(ge=1, strict=True)


INELIGIBLE_ASSIGNEE = "Choose an active colleague with current access to this list."


def _eligible(db: Session, todo_list: TodoList, user_id: uuid.UUID | None) -> User:
    """Return the assignee if active and allowed on the list; personal lists allow only the owner."""
    assignee = db.get(User, user_id) if user_id else None
    if assignee is None or not assignee.is_active:
        raise Invalid("ineligible_assignee", INELIGIBLE_ASSIGNEE)
    if todo_list.owner_id is not None:
        allowed = user_id == todo_list.owner_id
    else:
        allowed = policy.resolve(db, assignee, todo_list.workspace_id) is not None
    if not allowed:
        raise Invalid("ineligible_assignee", INELIGIBLE_ASSIGNEE)
    return assignee


def _candidate_user_ids(db: Session, user, todo_list: TodoList) -> set:
    """Everyone who may be assigned tasks on the list."""
    if todo_list.owner_id:
        return {todo_list.owner_id}
    access = policy.require_read(db, user, todo_list.workspace_id)
    return policy.eligible_reader_ids(db, access.workspace)


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards: directory search is literal, not a pattern language."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _person_json(person: User) -> dict:
    """The public fields of an assignable colleague."""
    return {"id": str(person.id), "display_name": person.display_name, "username": person.username}


@router.get("/lists/{list_id}/assignees")
def assignees(
    list_id: uuid.UUID,
    request: Request,
    q: str = Query(default="", max_length=100),
    after: uuid.UUID | None = None,
    limit: int = Query(default=25, ge=1, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    user = _actor(request, actor, db)
    todo_list = _list(db, user, list_id)
    candidate_ids = _candidate_user_ids(db, user, todo_list)
    query = select(User).where(User.id.in_(candidate_ids), User.is_active.is_(True))
    if q:
        pattern = "%" + _escape_like(q) + "%"
        query = query.where(
            or_(
                User.display_name.ilike(pattern, escape="\\"),
                User.username.ilike(pattern, escape="\\"),
            )
        )
    if after:
        query = query.where(User.id > after)
    people = db.scalars(query.order_by(User.id).limit(limit + 1)).all()
    result = {
        "items": [_person_json(person) for person in people[:limit]],
        "next_cursor": str(people[limit - 1].id) if len(people) > limit else None,
    }
    _list(db, _actor(request, actor, db), list_id)
    return result


@router.put("/lists/{list_id}/tasks/{task_id}/assignee")
def assign(
    list_id: uuid.UUID,
    task_id: uuid.UUID,
    body: Assignment,
    request: Request,
    *,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    # Preflight without taking target identity locks: unauthorized requests must
    # not acquire arbitrary colleagues' locks. Final authority is checked again.
    user = _actor(request, actor, db)
    todo_list = _list(db, user, list_id)
    if todo_list.workspace_id:
        policy.require_write(db, user, todo_list.workspace_id)
    if body.user_id:
        _eligible(db, todo_list, body.user_id)
    identity_ids = {user.id} | ({body.user_id} if body.user_id else set())
    # Deterministic order prevents reciprocal A->B / B->A assignment deadlocks.
    db.execute(
        select(User.id).where(User.id.in_(identity_ids)).order_by(User.id).with_for_update(key_share=True)
    )
    user = _actor(request, actor, db, True)
    todo_list = _list(db, user, list_id, True)
    new_assignee = _eligible(db, todo_list, body.user_id) if body.user_id else None
    task = db.get(TodoTask, task_id)
    if task is None or task.list_id != list_id:
        raise NotFound()
    if task.revision != body.revision:
        raise Conflict("revision_conflict", "This task changed. Refresh before assigning again.")
    if task.assignee_id == body.user_id:
        lock_identity(db, actor, get_settings(request))
        return _task_json(task)
    before = task_history.snapshot(task)
    task.assignee_id = body.user_id
    task.assignee = new_assignee
    task.revision += 1
    task.updated_at = utcnow()
    task_history.record(db, task, user.id, before)
    lock_identity(db, actor, get_settings(request))
    db.commit()
    task_events.publish_changed(request, todo_list.workspace_id)
    return _task_json(task)


def _my_task_json(task: TodoTask, todo_list: TodoList) -> dict:
    """A task plus the list title and workspace it appears under."""
    return {
        **_task_json(task),
        "list_title": todo_list.title,
        "workspace_id": str(todo_list.workspace_id) if todo_list.workspace_id else None,
    }


@router.get("/mine")
def mine(
    request: Request,
    status: State | None = None,
    after: uuid.UUID | None = None,
    limit: int = Query(default=25, ge=1, le=50),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    user = _actor(request, actor, db)
    user_id = user.id
    readable_ids = policy.readable_workspace_ids(db, user)
    own_or_assigned = or_(
        TodoList.owner_id == user.id,
        and_(TodoTask.assignee_id == user.id, TodoList.workspace_id.in_(readable_ids)),
    )
    query = select(TodoTask, TodoList).join(TodoList, TodoList.id == TodoTask.list_id).where(own_or_assigned)
    if status:
        query = query.where(TodoTask.status == status)
    if after:
        query = query.where(TodoTask.id > after)
    rows = db.execute(query.order_by(TodoTask.id).limit(limit + 1)).all()
    result = {
        "items": [_my_task_json(task, todo_list) for task, todo_list in rows[:limit]],
        "next_cursor": str(rows[limit - 1][0].id) if len(rows) > limit else None,
    }
    fresh_user = _actor(request, actor, db)
    if fresh_user.id != user_id:
        raise Unauthenticated()
    current_ids = {str(workspace_id) for workspace_id in policy.readable_workspace_ids(db, fresh_user)}
    result["items"] = [
        item
        for item in result["items"]
        if item["workspace_id"] is None or item["workspace_id"] in current_ids
    ]
    result["restart_required"] = current_ids != {str(workspace_id) for workspace_id in readable_ids}
    if result["restart_required"]:
        # A cursor/more-results signal must not reveal rows in a revoked scope.
        result["next_cursor"] = None
    return result
