"""Create tasks with protected, immutable board epoch/revision context."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import policy, task_events
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import Board, TodoSource, TodoTask, Workspace
from .todos import TaskCreate, _actor, _create_task_row, _digest, _list, _lock_source_read, _task_json

router = APIRouter(prefix="/todos", tags=["todos"])


class BoardConversion(TaskCreate):
    source_workspace_id: uuid.UUID
    source_epoch: int = Field(ge=1, strict=True)
    source_revision: int = Field(ge=0, strict=True)
    confirm_audience: bool = Field(default=False, strict=True)


def _board(db: Session, user, workspace_id: uuid.UUID, lock: bool = False) -> Board:
    """Load the board of a workspace the user can read; optionally hold a shared row lock."""
    policy.require_read(db, user, workspace_id)
    query = select(Board).where(Board.workspace_id == workspace_id)
    if lock:
        query = query.with_for_update(read=True)
    board = db.scalar(query.execution_options(populate_existing=True))
    if board is None:
        raise NotFound()
    return board


def require_audience_confirmation(target, source_workspace_id: uuid.UUID, confirmed: bool) -> None:
    """Refuse a copy into a different workspace audience unless the user confirmed it."""
    crosses_audience = target.workspace_id is not None and target.workspace_id != source_workspace_id
    if crosses_audience and not confirmed:
        raise Invalid(
            "audience_confirmation_required",
            "Confirm that this task copy will be shared with a different workspace audience.",
        )


def _has_creation_receipt(db: Session, user, client_id: uuid.UUID) -> bool:
    """True when this request id already created a task for the user."""
    existing_task_id = db.scalar(
        select(TodoTask.id).where(TodoTask.created_by == user.id, TodoTask.client_id == client_id)
    )
    return existing_task_id is not None


@router.get("/board-context/{workspace_id}")
def context(
    workspace_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    board = _board(db, _actor(request, actor, db), workspace_id)
    result = {"epoch": board.epoch, "revision": board.revision}
    _board(db, _actor(request, actor, db), workspace_id)
    return result


@router.post("/lists/{list_id}/from-board", status_code=201)
def convert(
    list_id: uuid.UUID,
    body: BoardConversion,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    user = _actor(request, actor, db, True)
    target = _list(db, user, list_id, True)
    _lock_source_read(db, user, target, body.source_workspace_id)
    board = _board(db, user, body.source_workspace_id, lock=True)
    require_audience_confirmation(target, board.workspace_id, body.confirm_audience)
    # A committed retry keeps its original context even after later ink/restore.
    # Never apply a current-revision test before checking for a creation receipt.
    requested_context = (body.source_epoch, body.source_revision)
    if not _has_creation_receipt(db, user, body.client_id) and requested_context != (
        board.epoch,
        board.revision,
    ):
        raise Conflict(
            "board_context_changed", "The board changed. Review its latest context before creating this task."
        )
    reviewed_fields = body.model_dump(
        exclude={"source_workspace_id", "source_epoch", "source_revision", "confirm_audience"}
    )
    row, created = _create_task_row(
        db, user, list_id, TaskCreate.model_validate(reviewed_fields), _digest(body, list_id)
    )
    if created:
        db.add(
            TodoSource(
                task_id=row.id,
                board_workspace_id=board.workspace_id,
                board_epoch=body.source_epoch,
                board_revision=body.source_revision,
            )
        )
    lock_identity(db, actor, get_settings(request))
    db.commit()
    if created:
        db.expire(row, ["source"])
        task_events.publish_changed(request, target.workspace_id)
    return _task_json(row)


def board_source(db: Session, request: Request, actor: Actor, list_id: uuid.UUID, reference) -> dict:
    """Describe the board a task was created from, re-checking access after reading."""
    user = _actor(request, actor, db)
    _list(db, user, list_id)
    board = _board(db, user, reference.board_workspace_id)
    workspace_id = board.workspace_id
    result = {
        "kind": "board",
        "workspace_id": str(board.workspace_id),
        "workspace_name": db.get(Workspace, board.workspace_id).name,
        "epoch": reference.board_epoch,
        "revision": reference.board_revision,
        "current_epoch": board.epoch,
        "current_revision": board.revision,
    }
    fresh_user = _actor(request, actor, db)
    _list(db, fresh_user, list_id)
    _board(db, fresh_user, workspace_id)
    return result
