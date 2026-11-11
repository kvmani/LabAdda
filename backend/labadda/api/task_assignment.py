"""C2 assignment and current-grant My Tasks; assignment never grants access."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .. import policy, task_history, task_events
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


def _eligible(db, row, user_id):
    target = db.get(User, user_id) if user_id else None
    if target is None or not target.is_active:
        raise Invalid("ineligible_assignee", "Choose an active colleague with current access to this list.")
    if row.owner_id is not None:
        allowed = user_id == row.owner_id
    else:
        allowed = policy.resolve(db, target, row.workspace_id) is not None
    if not allowed:
        raise Invalid("ineligible_assignee", "Choose an active colleague with current access to this list.")
    return target


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
    row = _list(db, user, list_id)
    ids = (
        {row.owner_id}
        if row.owner_id
        else policy.eligible_reader_ids(db, policy.require_read(db, user, row.workspace_id).workspace)
    )
    query = select(User).where(User.id.in_(ids), User.is_active.is_(True))
    if q:
        # Escape LIKE wildcards: directory search is literal, not a pattern language.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                User.display_name.ilike("%" + escaped + "%", escape="\\"),
                User.username.ilike("%" + escaped + "%", escape="\\"),
            )
        )
    if after:
        query = query.where(User.id > after)
    rows = db.scalars(query.order_by(User.id).limit(limit + 1)).all()
    result = {
        "items": [
            {"id": str(r.id), "display_name": r.display_name, "username": r.username} for r in rows[:limit]
        ],
        "next_cursor": str(rows[limit - 1].id) if len(rows) > limit else None,
    }
    _list(db, _actor(request, actor, db), list_id)
    return result


@router.put("/lists/{list_id}/tasks/{task_id}/assignee")
def assign(
    list_id: uuid.UUID,
    task_id: uuid.UUID,
    body: Assignment,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    # Preflight without taking target identity locks: unauthorized requests must
    # not acquire arbitrary colleagues' locks. Final authority is checked again.
    user = _actor(request, actor, db)
    row = _list(db, user, list_id)
    if row.workspace_id:
        policy.require_write(db, user, row.workspace_id)
    if body.user_id:
        _eligible(db, row, body.user_id)
    identities = {user.id} | ({body.user_id} if body.user_id else set())
    # Deterministic order prevents reciprocal A->B / B->A assignment deadlocks.
    db.execute(
        select(User.id).where(User.id.in_(identities)).order_by(User.id).with_for_update(key_share=True)
    )
    user = _actor(request, actor, db, True)
    row = _list(db, user, list_id, True)
    target = _eligible(db, row, body.user_id) if body.user_id else None
    task = db.get(TodoTask, task_id)
    if task is None or task.list_id != list_id:
        raise NotFound()
    if task.revision != body.revision:
        raise Conflict("revision_conflict", "This task changed. Refresh before assigning again.")
    if task.assignee_id == body.user_id:
        lock_identity(db, actor, get_settings(request))
        return _task_json(task)
    before = task_history.snapshot(task)
    task.assignee_id, task.assignee = body.user_id, target
    task.revision += 1
    task.updated_at = utcnow()
    task_history.record(db, task, user.id, before)
    lock_identity(db, actor, get_settings(request))
    db.commit()
    task_events.publish_changed(request, row.workspace_id)
    return _task_json(task)


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
    visible = policy.readable_workspace_ids(db, user)
    query = (
        select(TodoTask, TodoList)
        .join(TodoList, TodoList.id == TodoTask.list_id)
        .where(
            or_(
                TodoList.owner_id == user.id,
                and_(TodoTask.assignee_id == user.id, TodoList.workspace_id.in_(visible)),
            )
        )
    )
    if status:
        query = query.where(TodoTask.status == status)
    if after:
        query = query.where(TodoTask.id > after)
    rows = db.execute(query.order_by(TodoTask.id).limit(limit + 1)).all()
    result = {
        "items": [
            {
                **_task_json(task),
                "list_title": row.title,
                "workspace_id": str(row.workspace_id) if row.workspace_id else None,
            }
            for task, row in rows[:limit]
        ],
        "next_cursor": str(rows[limit - 1][0].id) if len(rows) > limit else None,
    }
    fresh = _actor(request, actor, db)
    if fresh.id != user_id:
        raise Unauthenticated()
    current = {str(key) for key in policy.readable_workspace_ids(db, fresh)}
    result["items"] = [
        item for item in result["items"] if item["workspace_id"] is None or item["workspace_id"] in current
    ]
    result["restart_required"] = current != {str(key) for key in visible}
    if result["restart_required"]:
        # A cursor/more-results signal must not reveal rows in a revoked scope.
        result["next_cursor"] = None
    return result
