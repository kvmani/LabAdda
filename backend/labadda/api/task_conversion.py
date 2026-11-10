"""Conversation-to-task conversion with explicit audience and protected provenance."""
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import policy, task_events
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import ChatMessage, Post, TodoSource, TodoTask, Workspace
from ..serialize import iso
from .todos import TaskCreate, _actor, _create_task_row, _digest, _list, _task_json

router = APIRouter(prefix='/todos', tags=['todos'])


class Conversion(TaskCreate):
    source_kind: Literal['post', 'chat']
    source_id: uuid.UUID
    confirm_audience: bool = Field(default=False, strict=True)


def _source(db, user, kind, source_id, lock=False):
    model = Post if kind == 'post' else ChatMessage
    query = select(model).where(model.id == source_id)
    if lock:
        query = query.with_for_update(read=True)
    row = db.scalar(query.execution_options(populate_existing=True))
    if row is None or (kind == 'post' and (row.deleted_at is not None or row.parent_id is not None)):
        raise NotFound()
    policy.require_read(db, user, row.workspace_id)
    return row


@router.post('/lists/{list_id}/from-conversation', status_code=201)
def convert(list_id: uuid.UUID, body: Conversion, request: Request,
            actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    # Destination lock order matches task writes; membership/workspace SHARE locks
    # serialize both source-read and destination-write authority with revocation.
    target = _list(db, user, list_id, True)
    source = _source(db, user, body.source_kind, body.source_id)
    if target.workspace_id is None:
        db.execute(select(Workspace.id).where(Workspace.id == source.workspace_id)
                   .with_for_update(read=True, key_share=True))
        db.execute(text('lock table workspaces, memberships in share mode'))
        db.expire_all()
        source = _source(db, user, body.source_kind, body.source_id)
    source = _source(db, user, body.source_kind, body.source_id, lock=True)
    if target.workspace_id is not None and target.workspace_id != source.workspace_id and not body.confirm_audience:
        raise Invalid('audience_confirmation_required', 'Confirm that this task copy will be shared with a different workspace audience.')
    # No automatic source text or author copy: only fields the user reviews here.
    task_body = TaskCreate.model_validate(body.model_dump(exclude={'source_kind', 'source_id', 'confirm_audience'}))
    row, created = _create_task_row(db, user, list_id, task_body, _digest(body, list_id))
    if created:
        db.add(TodoSource(task_id=row.id,
                          post_id=source.id if body.source_kind == 'post' else None,
                          chat_message_id=source.id if body.source_kind == 'chat' else None))
    lock_identity(db, actor, get_settings(request))
    db.commit()
    if created:
        # The new reference must be visible in the compatible task representation.
        db.expire(row, ['source'])
        task_events.publish_changed(request, target.workspace_id)
    return _task_json(row)


@router.get('/lists/{list_id}/tasks/{task_id}/source')
def source(list_id: uuid.UUID, task_id: uuid.UUID, request: Request,
           actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    _list(db, user, list_id)
    task = db.get(TodoTask, task_id)
    if task is None or task.list_id != list_id:
        raise NotFound()
    reference = db.get(TodoSource, task_id)
    if reference is None or (reference.post_id is None and reference.chat_message_id is None):
        raise NotFound()
    kind = 'post' if reference.post_id else 'chat'
    row = _source(db, user, kind, reference.post_id or reference.chat_message_id)
    result = {'kind': kind, 'id': str(row.id), 'workspace_id': str(row.workspace_id),
              'workspace_name': db.get(Workspace, row.workspace_id).name, 'body': row.body,
              'created_at': iso(row.created_at)}
    fresh = _actor(request, actor, db)
    _list(db, fresh, list_id)
    _source(db, fresh, kind, row.id)
    return result
