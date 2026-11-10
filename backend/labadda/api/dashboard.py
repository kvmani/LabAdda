"""Bounded personal collaboration overview; never a site-wide content inventory."""
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,Request
from sqlalchemy import and_,case,func,or_,select
from sqlalchemy.orm import Session
from .. import policy
from ..deps import Actor,current_actor,get_db,get_settings
from ..models import ChatMessage,ChatRead,Note,TodoList,TodoTask,Workspace
from ..security import utcnow
from ..serialize import iso
from .todos import _actor,_task_json
from .notifications import _visible

router=APIRouter(tags=['dashboard'])


@router.get('/dashboard')
def overview(request:Request,actor:Actor=Depends(current_actor),db:Session=Depends(get_db)):
    user=_actor(request,actor,db);visible=set(policy.readable_workspace_ids(db,user))
    workspaces={row.id:row.name for row in db.scalars(select(Workspace).where(Workspace.id.in_(visible)))}
    query=select(TodoTask,TodoList).join(TodoList,TodoTask.list_id==TodoList.id).where(
        TodoTask.done.is_(False),or_(TodoList.owner_id==user.id,and_(TodoTask.assignee_id==user.id,TodoList.workspace_id.in_(visible))))
    rows=db.execute(query.order_by(TodoTask.due_date.asc().nulls_last(),case((TodoTask.priority=='high',0),(TodoTask.priority=='normal',1),else_=2),TodoTask.id).limit(26)).all()
    tasks=[{**_task_json(task),'list_title':listing.title,'workspace_id':str(listing.workspace_id) if listing.workspace_id else None,
            'workspace_name':workspaces.get(listing.workspace_id)} for task,listing in rows[:25]]
    notes=db.scalars(select(Note).where(Note.owner_id==user.id,Note.due_at.is_not(None)).order_by(Note.due_at,Note.id).limit(11)).all()
    note_items=[{'id':str(row.id),'title':row.title,'due_at':iso(row.due_at)} for row in notes[:10]]
    unread=db.execute(select(ChatMessage.workspace_id,func.count()).outerjoin(ChatRead,and_(ChatRead.workspace_id==ChatMessage.workspace_id,ChatRead.user_id==user.id)).where(
        ChatMessage.workspace_id.in_(visible),ChatMessage.author_id!=user.id,ChatMessage.seq>func.coalesce(ChatRead.last_seq,0)).group_by(ChatMessage.workspace_id)).all()
    chats=[{'workspace_id':str(ws),'workspace_name':workspaces[ws],'unread':count} for ws,count in unread]
    fresh=_actor(request,actor,db);current=set(policy.readable_workspace_ids(db,fresh))
    updates=[{'id':str(row.id),'kind':row.kind,'created_at':iso(row.created_at),'read':row.read_at is not None,**info} for row,info in _visible(db,actor,10)]
    final=set(policy.readable_workspace_ids(db,_actor(request,actor,db)))
    allowed={str(ws) for ws in final};changed=final!=visible or current!=visible
    tasks=[row for row in tasks if row['workspace_id'] is None or row['workspace_id'] in allowed]
    chats=[row for row in chats if row['workspace_id'] in allowed]
    updates=[row for row in updates if row['workspace'] is None or row['workspace']['id'] in allowed]
    timezone=get_settings(request).timezone
    return {'today':utcnow().astimezone(ZoneInfo(timezone)).date().isoformat(),'timezone':timezone,
            'tasks':tasks,'tasks_more':len(rows)>25 and not changed,'notes':note_items,'notes_more':len(notes)>10,
            'updates':updates,'chats':sorted(chats,key=lambda row:(-row['unread'],row['workspace_name']))[:10],
            'chats_more':len(chats)>10 and not changed,'restart_required':changed,'observed_at':iso(utcnow())}
