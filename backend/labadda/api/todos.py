"""C1 scoped to-do lists: bounded requests, durable creation and revisioned edits."""
from datetime import date
import hashlib
import json
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import policy
from ..deps import Actor, PANEL_HEADER, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound, Unauthenticated
from ..identity_locks import lock_identity
from ..models import TodoList, TodoTask, Workspace
from ..security import utcnow
from ..serialize import iso

router = APIRouter(prefix='/todos', tags=['todos'])


class Title(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200, strict=True)

    @field_validator('title')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Write a title')
        return value.strip()


class ListCreate(Title):
    client_id: uuid.UUID
    workspace_id: uuid.UUID | None = None


class ListEdit(Title):
    revision: int = Field(ge=1, strict=True)


class CheckItem(Title):
    done: bool = Field(default=False, strict=True)


class TaskFields(Title):
    description: str = Field(default='', max_length=10000, strict=True)
    due_date: date | None = None
    priority: Literal['low','normal','high'] = 'normal'
    checklist: list[CheckItem] = Field(default_factory=list, max_length=50)
    done: bool = Field(default=False, strict=True)


class TaskCreate(TaskFields):
    client_id: uuid.UUID


class TaskEdit(TaskFields):
    revision: int = Field(ge=1, strict=True)


def _actor(request, actor, db, write=False):
    if request.headers.get(PANEL_HEADER) or request.query_params.get('panel') == '1':
        raise Unauthenticated()
    db.execute(text("set local lock_timeout = '2s'"))
    db.execute(text("set local statement_timeout = '3s'"))
    if write:
        return lock_identity(db, actor, get_settings(request))
    db.expire_all()
    return current_actor(request, db).user


def _scope(db, user, workspace_id, write=False):
    if workspace_id is not None:
        if write:
            # Short SHARE table locks serialize task authorization with all
            # membership/tree/policy mutations, including ancestor grant changes.
            db.execute(select(Workspace.id).where(Workspace.id == workspace_id)
                       .with_for_update(read=True, key_share=True))
            db.execute(text('lock table workspaces, memberships in share mode'))
            db.expire_all()
        return (policy.require_write if write else policy.require_read)(db, user, workspace_id)


def _list(db, user, list_id, write=False):
    row = db.get(TodoList, list_id)
    if row is None or (row.owner_id is not None and row.owner_id != user.id):
        raise NotFound()
    _scope(db, user, row.workspace_id, write)
    if write:
        row = db.scalar(select(TodoList).where(TodoList.id == list_id).with_for_update()
                        .execution_options(populate_existing=True))
    return row


def _digest(body, scope):
    return hashlib.sha256(json.dumps({'body':body.model_dump(mode='json'), 'scope':str(scope)},
                                    sort_keys=True, separators=(',',':')).encode()).hexdigest()


def _list_json(row):
    return {'id':str(row.id), 'title':row.title, 'workspace_id':str(row.workspace_id) if row.workspace_id else None,
            'revision':row.revision, 'created_at':iso(row.created_at)}


def _task_json(row):
    return {'id':str(row.id), 'list_id':str(row.list_id), 'title':row.title, 'description':row.description,
            'due_date':row.due_date.isoformat() if row.due_date else None, 'priority':row.priority,
            'checklist':row.checklist, 'done':row.done, 'revision':row.revision, 'updated_at':iso(row.updated_at)}


def _page(db, query, model, after, limit, serialize):
    if after:
        query = query.where(model.id > after)
    rows = db.scalars(query.order_by(model.id).limit(limit+1)).all()
    return {'items':[serialize(r) for r in rows[:limit]],
            'next_cursor':str(rows[limit-1].id) if len(rows)>limit else None}


@router.get('/lists')
def lists(request: Request, workspace_id: uuid.UUID | None = None, after: uuid.UUID | None = None,
          limit: int = Query(default=25, ge=1, le=50), actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    _scope(db, user, workspace_id)
    query = select(TodoList).where(TodoList.workspace_id == workspace_id) if workspace_id else select(TodoList).where(TodoList.owner_id == user.id)
    result = _page(db, query, TodoList, after, limit, _list_json)
    _scope(db, _actor(request, actor, db), workspace_id)
    return result


@router.post('/lists', status_code=201)
def create_list(body: ListCreate, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    _scope(db, user, body.workspace_id, True)
    db.execute(text('select pg_advisory_xact_lock(hashtextextended(:scope,0))'),
               {'scope':'todo-lists:' + str(body.workspace_id or user.id)})
    fingerprint = _digest(body, body.workspace_id)
    row = db.scalar(select(TodoList).where(TodoList.created_by == user.id, TodoList.client_id == body.client_id))
    if row:
        if row.create_digest != fingerprint:
            raise Conflict('request_reused', 'This request ID already names a different list.')
        lock_identity(db, actor, get_settings(request))
        return _list_json(row)
    scope = TodoList.workspace_id == body.workspace_id if body.workspace_id else TodoList.owner_id == user.id
    if db.scalar(select(func.count()).select_from(TodoList).where(scope)) >= 100:
        raise Invalid('list_limit', 'This scope already has 100 lists.')
    row = TodoList(owner_id=None if body.workspace_id else user.id, workspace_id=body.workspace_id,
                   created_by=user.id, client_id=body.client_id, create_digest=fingerprint, title=body.title, revision=1)
    db.add(row)
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _list_json(row)


@router.put('/lists/{list_id}')
def edit_list(list_id: uuid.UUID, body: ListEdit, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    row = _list(db, user, list_id, True)
    if row.revision != body.revision:
        raise Conflict('revision_conflict', 'This list changed. Refresh before saving again.')
    row.title, row.revision = body.title, row.revision+1
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _list_json(row)


@router.get('/lists/{list_id}/tasks')
def tasks(list_id: uuid.UUID, request: Request, after: uuid.UUID | None = None,
          limit: int = Query(default=25, ge=1, le=50), actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    _list(db, user, list_id)
    result = _page(db, select(TodoTask).where(TodoTask.list_id == list_id), TodoTask, after, limit, _task_json)
    _list(db, _actor(request, actor, db), list_id)
    return result


@router.post('/lists/{list_id}/tasks', status_code=201)
def create_task(list_id: uuid.UUID, body: TaskCreate, request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    _list(db, user, list_id, True)
    fingerprint = _digest(body, list_id)
    row = db.scalar(select(TodoTask).where(TodoTask.created_by == user.id, TodoTask.client_id == body.client_id))
    if row:
        if row.create_digest != fingerprint:
            raise Conflict('request_reused', 'This request ID already names a different task.')
        lock_identity(db, actor, get_settings(request))
        return _task_json(row)
    if db.scalar(select(func.count()).select_from(TodoTask).where(TodoTask.list_id == list_id)) >= 2000:
        raise Invalid('task_limit', 'This list already has 2,000 tasks.')
    row = TodoTask(list_id=list_id, created_by=user.id, create_digest=fingerprint,
                   **body.model_dump(exclude={'checklist'}), checklist=[c.model_dump() for c in body.checklist], revision=1)
    db.add(row)
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _task_json(row)


@router.put('/lists/{list_id}/tasks/{task_id}')
def edit_task(list_id: uuid.UUID, task_id: uuid.UUID, body: TaskEdit, request: Request,
              actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db, True)
    _list(db, user, list_id, True)
    row = db.get(TodoTask, task_id)
    if row is None or row.list_id != list_id:
        raise NotFound()
    if row.revision != body.revision:
        raise Conflict('revision_conflict', 'This task changed. Refresh and review before saving again.')
    for key, value in body.model_dump(exclude={'revision'}).items():
        setattr(row, key, value)
    row.revision += 1
    row.updated_at = utcnow()
    lock_identity(db, actor, get_settings(request))
    db.commit()
    return _task_json(row)


@router.get('/lists/{list_id}/tasks/{task_id}')
def task(list_id: uuid.UUID, task_id: uuid.UUID, request: Request,
         actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    _list(db, user, list_id)
    row = db.get(TodoTask, task_id)
    if row is None or row.list_id != list_id:
        raise NotFound()
    result = _task_json(row)
    _list(db, _actor(request, actor, db), list_id)
    return result


@router.get('/lists/{list_id}')
def get_list(list_id: uuid.UUID, request: Request,
             actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    row = _list(db, _actor(request, actor, db), list_id)
    result = _list_json(row)
    _list(db, _actor(request, actor, db), list_id)
    return result
