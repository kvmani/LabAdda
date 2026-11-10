"""C2 workflow compatibility, scoped history and migration evidence."""
import hashlib
import json
import uuid

from alembic import command
import pytest
from sqlalchemy import select, text

from labadda.cli import alembic_config
from labadda.models import TodoTask
from tests.test_todos import new_list, task_body


def edit_fields(task, **changes):
    return {**{k:task[k] for k in ['title','description','due_date','priority','checklist','done','revision']},**changes}


def test_workflow_history_and_old_client_compatibility(as_user):
    api=as_user('ben'); row=new_list(api); path=f"/todos/lists/{row['id']}/tasks"
    body=task_body(); task=api.post(path,json=body).json()
    assert task['status']=='todo'
    assert len(api.get(path+'/'+task['id']+'/history').json()['items'])==1
    assert api.post(path,json=body).json()['id']==task['id']
    for state in ['in_progress','blocked','done','todo']:
        task=api.put(path+'/'+task['id'],json=edit_fields(task,status=state,done=state=='done')).json()
        assert task['status']==state
    events=api.get(path+'/'+task['id']+'/history?limit=2').json()
    assert [r['revision'] for r in events['items']]==[5,4]
    assert events['items'][0]['changes']['status']=={'before':'done','after':'todo'}
    next_page=api.get(path+'/'+task['id']+'/history?before='+str(events['next_cursor'])).json()
    assert [r['revision'] for r in next_page['items']]==[3,2,1]
    task=api.put(path+'/'+task['id'],json=edit_fields(task,status='blocked')).json()
    task=api.put(path+'/'+task['id'],json=edit_fields(task,title='Old client edited title')).json()
    assert task['status']=='blocked'  # omitted state preserves intermediate workflow
    task=api.put(path+'/'+task['id'],json=edit_fields(task,done=True)).json()
    assert task['status']=='done'
    task=api.put(path+'/'+task['id'],json=edit_fields(task,done=False)).json()
    assert task['status']=='todo'


def test_history_is_scoped_like_content(as_user,ids):
    api=as_user('ben'); row=new_list(api); path=f"/todos/lists/{row['id']}/tasks"
    task=api.post(path,json=task_body()).json(); history=path+'/'+task['id']+'/history'
    assert api.get(history,headers={'X-LabAdda-Panel':'1'}).status_code==401
    for name in ['admin','asha','chen','dana']:
        assert as_user(name).get(history).status_code==404
    shared=new_list(api,ids['workspaces']['section_a']); path=f"/todos/lists/{shared['id']}/tasks"
    task=api.post(path,json=task_body()).json()
    assert as_user('asha').get(path+'/'+task['id']+'/history').status_code==200
    assert as_user('dana').get(path+'/'+task['id']+'/history').status_code==404
    assert api.get(f"/todos/lists/{row['id']}/tasks/{task['id']}/history").status_code==404
    assert as_user('admin').delete(f"/admin/workspaces/{ids['workspaces']['section_a']}/memberships/{ids['users']['ben']}").status_code==200
    assert api.get(path+'/'+task['id']+'/history').status_code==404


@pytest.mark.parametrize('state,done',[('blocked',True),('done',False),('unknown',False)])
def test_invalid_workflow_cannot_change_task_or_history(as_user,state,done):
    api=as_user('ben'); row=new_list(api); path=f"/todos/lists/{row['id']}/tasks"
    task=api.post(path,json=task_body()).json()
    assert api.put(path+'/'+task['id'],json=edit_fields(task,status=state,done=done)).status_code==422
    assert len(api.get(path+'/'+task['id']+'/history').json()['items'])==1


def test_history_failure_rolls_back_task_change(as_user,monkeypatch):
    from labadda import task_history
    api=as_user('ben'); row=new_list(api); path=f"/todos/lists/{row['id']}/tasks"
    task=api.post(path,json=task_body()).json()
    def unavailable(*args,**kwargs): raise RuntimeError('synthetic history unavailable')
    monkeypatch.setattr(task_history,'record',unavailable)
    with pytest.raises(RuntimeError):
        api.put(path+'/'+task['id'],json=edit_fields(task,title='Must roll back'))
    assert api.get(path+'/'+task['id']).json()['title']==task['title']


def test_migration_preserves_c1_request_replay_and_records_baseline(as_user,settings,db_factory):
    api=as_user('ben'); row=new_list(api)
    cfg=alembic_config(settings.database_url)
    command.downgrade(cfg,'0017')
    body=task_body(done=False)
    digest=hashlib.sha256(json.dumps({'body':body,'scope':row['id']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    task_id=uuid.uuid4()
    from labadda.models import TodoList
    with db_factory() as db:
        creator=db.get(TodoList,row['id']).created_by
        db.execute(text("insert into todo_tasks(id,list_id,created_by,client_id,create_digest,title,description,due_date,priority,checklist,done,revision) values(:id,:list,:creator,:client,:digest,:title,:description,:due,:priority,cast(:checklist as jsonb),false,7)"),
                   {'id':task_id,'list':row['id'],'creator':creator,'client':body['client_id'],'digest':digest,
                    'title':body['title'],'description':body['description'],'due':body['due_date'],
                    'priority':body['priority'],'checklist':json.dumps(body['checklist'])})
        db.commit()
    command.upgrade(cfg,'head')
    path=f"/todos/lists/{row['id']}/tasks"
    replay=api.post(path,json=body)
    assert replay.status_code==201, replay.text
    assert replay.json()['id']==str(task_id) and replay.json()['revision']==7
    history=api.get(path+'/'+str(task_id)+'/history').json()['items']
    assert history[0]['action']=='baseline' and history[0]['actor_id'] is None and history[0]['changes']=={}
    with pytest.raises(RuntimeError,match='Task history exists'):
        command.downgrade(cfg,'0017')
