"""Bounded immutable discussions; current task/list policy on reads and writes."""

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import task_events
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import TodoComment, TodoList, TodoTask
from ..serialize import iso
from .todos import _actor, _list

router = APIRouter(prefix="/todos", tags=["todos"])


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: uuid.UUID
    body: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("body")
    @classmethod
    def meaningful(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Write a comment")
        return value.strip()


MAX_COMMENTS_PER_TASK = 1000


def _task(db: Session, user, list_id: uuid.UUID, task_id: uuid.UUID, write: bool = False) -> TodoTask:
    """Load a task of a list the user may use; a task of another list is missing."""
    _list(db, user, list_id, write)
    task = db.get(TodoTask, task_id)
    if task is None or task.list_id != list_id:
        raise NotFound()
    return task


def _json(comment: TodoComment) -> dict:
    """Serialize a comment with its author's display name."""
    return {
        "id": str(comment.id),
        "sequence": comment.sequence,
        "body": comment.body,
        "created_at": iso(comment.created_at),
        "author": {"id": str(comment.author_id), "display_name": comment.author.display_name},
    }


def _request_digest(task_id: uuid.UUID, text: str) -> str:
    """Fingerprint of a comment request, so a reused request id with other text is detectable."""
    canonical = json.dumps({"task_id": str(task_id), "body": text}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _next_sequence(db: Session, task_id: uuid.UUID) -> int:
    """The next comment number; the list row lock serializes this with other writers."""
    highest = db.scalar(select(func.max(TodoComment.sequence)).where(TodoComment.task_id == task_id))
    sequence = (highest or 0) + 1
    if sequence > MAX_COMMENTS_PER_TASK:
        raise Invalid("comment_limit", "This task already has 1,000 comments.")
    return sequence


@router.get("/lists/{list_id}/tasks/{task_id}/comments")
def comments(
    list_id: uuid.UUID,
    task_id: uuid.UUID,
    request: Request,
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=25, ge=1, le=50),
    *,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    _task(db, _actor(request, actor, db), list_id, task_id)
    query = select(TodoComment).where(TodoComment.task_id == task_id)
    if before is not None:
        query = query.where(TodoComment.sequence < before)
    newest_first = db.scalars(query.order_by(TodoComment.sequence.desc()).limit(limit + 1)).all()
    result = {
        "items": [_json(comment) for comment in newest_first[:limit]],
        "next_cursor": newest_first[limit - 1].sequence if len(newest_first) > limit else None,
    }
    _task(db, _actor(request, actor, db), list_id, task_id)
    return result


@router.post("/lists/{list_id}/tasks/{task_id}/comments", status_code=201)
def comment(
    list_id: uuid.UUID,
    task_id: uuid.UUID,
    body: CommentCreate,
    request: Request,
    *,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    user = _actor(request, actor, db, True)
    _task(db, user, list_id, task_id, True)
    digest = _request_digest(task_id, body.body)
    earlier = db.scalar(
        select(TodoComment).where(TodoComment.author_id == user.id, TodoComment.client_id == body.client_id)
    )
    if earlier:
        if earlier.create_digest != digest:
            raise Conflict("request_reused", "This request ID already names a different comment.")
        lock_identity(db, actor, get_settings(request))
        return _json(earlier)
    new_comment = TodoComment(
        task_id=task_id,
        author_id=user.id,
        client_id=body.client_id,
        create_digest=digest,
        sequence=_next_sequence(db, task_id),
        body=body.body,
        created_at=db.scalar(select(func.clock_timestamp())),
    )
    db.add(new_comment)
    lock_identity(db, actor, get_settings(request))
    workspace_id = db.get(TodoList, list_id).workspace_id
    db.commit()
    task_events.publish_changed(request, workspace_id)
    return _json(new_comment)
