"""Bounded immutable discussions; current task/list policy on reads and writes."""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Conflict, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import TodoComment, TodoTask
from .todos import _actor, _list
from ..serialize import iso

router = APIRouter(prefix='/todos',tags=['todos'])


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    client_id: uuid.UUID
    body: str = Field(min_length=1,max_length=4000,strict=True)

    @field_validator('body')
    @classmethod
    def meaningful(cls,value):
        if not value.strip():
            raise ValueError('Write a comment')
        return value.strip()


def _task(db,user,list_id,task_id,write=False):
    _list(db,user,list_id,write)
    row = db.get(TodoTask,task_id)
    if row is None or row.list_id != list_id:
        raise NotFound()
    return row


def _json(row):
    return {'id':str(row.id),'sequence':row.sequence,'body':row.body,'created_at':iso(row.created_at),
            'author':{'id':str(row.author_id),'display_name':row.author.display_name}}


@router.get('/lists/{list_id}/tasks/{task_id}/comments')
def comments(list_id: uuid.UUID, task_id: uuid.UUID, request: Request,
             before: int | None = Query(default=None,ge=1), limit: int = Query(default=25,ge=1,le=50),
             actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    _task(db,_actor(request,actor,db),list_id,task_id)
    query = select(TodoComment).where(TodoComment.task_id == task_id)
    if before is not None:
        query = query.where(TodoComment.sequence < before)
    rows = db.scalars(query.order_by(TodoComment.sequence.desc()).limit(limit+1)).all()
    result = {'items':[_json(row) for row in rows[:limit]],
              'next_cursor':rows[limit-1].sequence if len(rows)>limit else None}
    _task(db,_actor(request,actor,db),list_id,task_id)
    return result


@router.post('/lists/{list_id}/tasks/{task_id}/comments',status_code=201)
def comment(list_id: uuid.UUID, task_id: uuid.UUID, body: CommentCreate, request: Request,
            actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request,actor,db,True)
    _task(db,user,list_id,task_id,True)
    digest = hashlib.sha256(json.dumps({'task_id':str(task_id),'body':body.body},
                                       sort_keys=True,separators=(',',':')).encode()).hexdigest()
    row = db.scalar(select(TodoComment).where(TodoComment.author_id == user.id,TodoComment.client_id == body.client_id))
    if row:
        if row.create_digest != digest:
            raise Conflict('request_reused','This request ID already names a different comment.')
        lock_identity(db,actor,get_settings(request))
        return _json(row)
    # The list row lock serializes append sequence/capacity with other writers.
    sequence = (db.scalar(select(func.max(TodoComment.sequence)).where(TodoComment.task_id == task_id)) or 0)+1
    if sequence > 1000:
        raise Invalid('comment_limit','This task already has 1,000 comments.')
    row = TodoComment(task_id=task_id,author_id=user.id,client_id=body.client_id,create_digest=digest,
                      sequence=sequence,body=body.body,created_at=db.scalar(select(func.clock_timestamp())))
    db.add(row)
    lock_identity(db,actor,get_settings(request))
    db.commit()
    return _json(row)
