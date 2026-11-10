import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api } from '../api';
import { useTaskUpdates } from '../taskUpdates';
import { TaskAssignment, type Assignee } from '../components/TaskAssignment';
import { TaskSource } from '../components/TaskSource';
import { TaskComments } from '../components/TaskComments';
import { TaskHistory } from '../components/TaskHistory';
import type { Workspace } from '../types';

type List = {id: string; title: string; revision: number; workspace_id: string | null};
type Workflow = 'todo' | 'in_progress' | 'blocked' | 'done';
const workflowLabels: Record<Workflow,string> = {todo:'To do',in_progress:'In progress',blocked:'Blocked',done:'Done'};
type Fields = {status: Workflow; title: string; description: string; due_date: string | null; priority: string; checklist: {title: string; done: boolean}[]; done: boolean};
type Task = Fields & {has_source:boolean;assignee:Assignee|null;id: string; revision: number};
type Page<T> = {items: T[]; next_cursor: string | null};
const blank = (): Fields => ({status:'todo',title:'', description:'', due_date:null, priority:'normal', checklist:[], done:false});
const uncertain = (error: any) => error.status === 0 || error.status >= 500;

function TaskEditor({listId, initial, saved, cancel}: {listId: string; initial: Task | null; saved: () => void; cancel: () => void}) {
  const [fields, setFields] = useState<Fields>(initial ?? blank());
  const [revision, setRevision] = useState(initial?.revision ?? 1);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [conflict, setConflict] = useState(false);
  const attempt = useRef<{client_id:string} & Fields | null>(null);
  const path = `/todos/lists/${listId}/tasks`;
  async function submit(event: FormEvent) {
    event.preventDefault(); if(busy)return; setBusy(true); setError(''); setConflict(false);
    try {
      if (initial) {
        const {title,description,due_date,priority,checklist,done,status} = fields;
        await api(`${path}/${initial.id}`, {method:'PUT',body:{title,description,due_date,priority,checklist,done,status,revision}});
      } else {
        attempt.current ??= {...fields,client_id:crypto.randomUUID()};
        await api(path,{body:attempt.current});
      }
      saved();
    } catch (e: any) {
      setError(e.message); setConflict(e.status === 409);
      if (!initial) { setUnconfirmed(uncertain(e)); if (!uncertain(e)) attempt.current=null; }
    } finally { setBusy(false); }
  }
  async function latest() {
    setBusy(true); setError('');
    try {
      const result = await api<Task>(`${path}/${initial!.id}`);
      setFields(result); setRevision(result.revision); setConflict(false);
    } catch(e: any) {setError(e.message);} finally {setBusy(false);}
  }
  return <form onSubmit={submit} className="card todo-editor">
    <h3>{initial ? 'Edit task' : 'New task'}</h3>
    <fieldset disabled={busy || unconfirmed}>
      <label>Task title<input required maxLength={200} value={fields.title} onChange={e=>setFields({...fields,title:e.target.value})} /></label>
      <label>Description<textarea aria-label="Description" maxLength={10000} value={fields.description} onChange={e=>setFields({...fields,description:e.target.value})} /></label>
      <label>Due date<input type="date" value={fields.due_date ?? ''} onChange={e=>setFields({...fields,due_date:e.target.value || null})} /></label>
      <label>Priority<select aria-label="Priority" value={fields.priority} onChange={e=>setFields({...fields,priority:e.target.value})}>{['low','normal','high'].map(p=><option key={p}>{p}</option>)}</select></label>
      <label>Workflow state<select aria-label="Workflow state" value={fields.status} onChange={e=>{const status=e.target.value as Workflow;setFields({...fields,status,done:status==='done'});}}>{Object.entries(workflowLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label><input type="checkbox" checked={fields.done} onChange={e=>setFields({...fields,done:e.target.checked,status:e.target.checked?'done':'todo'})} />Task completed</label>
      <h4>Checklist</h4>
      {fields.checklist.map((item,index)=><div className="todo-check" key={index}>
        <input aria-label={`Checklist item ${index+1} done`} type="checkbox" checked={item.done} onChange={e=>setFields({...fields,checklist:fields.checklist.map((v,i)=>i===index?{...v,done:e.target.checked}:v)})} />
        <input aria-label={`Checklist item ${index+1} title`} required maxLength={200} value={item.title} onChange={e=>setFields({...fields,checklist:fields.checklist.map((v,i)=>i===index?{...v,title:e.target.value}:v)})} />
        <button type="button" onClick={()=>setFields({...fields,checklist:fields.checklist.filter((_,i)=>i!==index)})}>Remove item {index+1}</button>
      </div>)}
      <button type="button" disabled={fields.checklist.length>=50} onClick={()=>setFields({...fields,checklist:[...fields.checklist,{title:'',done:false}]})}>Add checklist item</button>
    </fieldset>
    {error && <p role="alert" className="error">{error}</p>}
    {unconfirmed && <p role="status">Creation is unconfirmed. Retry the same request to recover its result; these fields are kept unchanged.</p>}
    {conflict && <p>Your draft is kept. Copy any changes you need before loading the latest task.</p>}
    {conflict && initial && <button type="button" disabled={busy} onClick={latest}>Load latest task (replaces draft)</button>}
    <button type="submit" disabled={busy}>{busy ? 'Saving…' : unconfirmed ? 'Retry same task creation' : 'Save task'}</button>
    <button type="button" disabled={busy} onClick={cancel}>Close editor</button>
  </form>;
}

export function Todos({ws}: {ws?: Workspace}) {
  const [lists,setLists] = useState<List[]>([]), [listCursor,setListCursor] = useState<string|null>(null);
  const [selected,setSelected] = useState<List|null>(null);
  const [tasks,setTasks] = useState<Task[]>([]), [taskCursor,setTaskCursor] = useState<string|null>(null);
  const [title,setTitle] = useState(''), [rename,setRename] = useState('');
  const [error,setError] = useState(''), [message,setMessage] = useState('');
  const [busy,setBusy] = useState(false), [loading,setLoading] = useState(true), [taskLoading,setTaskLoading] = useState(false);
  const [creating,setCreating] = useState(false), [editing,setEditing] = useState<Task|null>(null), [editorKey,setEditorKey] = useState(0);
  const [unconfirmed,setUnconfirmed] = useState(false);
  const [renameConflict,setRenameConflict] = useState(false);
  const listAttempt=useRef<{client_id:string;title:string;workspace_id:string|null}|null>(null);
  const selectedRef=useRef<string|null>(null);
  const generation=useRef(0), taskGeneration=useRef(0), editorGeneration=useRef(0);
  const writable = ws ? ws.can_write && !ws.archived : true;
  function failed(e: any) {
    setError(e.message);
    if ([401,403,404].includes(e.status)) {++generation.current;++taskGeneration.current;++editorGeneration.current;setLoading(false);setTaskLoading(false);setListCursor(null);setTaskCursor(null);setLists([]);selectedRef.current=null;setSelected(null);setTasks([]);setCreating(false);setEditing(null);}
  }
  const updates=useTaskUpdates(ws ? [ws.id] : [],()=>failed({status:404,message:"This workspace is no longer available."}));
  async function loadLists(after?: string) {
    const token=++generation.current; setLoading(true); setError('');
    try {
      const result=await api<Page<List>>('/todos/lists',{params:{workspace_id:ws?.id,after}});
      if(token===generation.current) {setLists(result.items);setListCursor(result.next_cursor);return true;}
      return false;
    } catch(e:any) {if(token===generation.current) failed(e);return false;} finally {if(token===generation.current) setLoading(false);}
  }
  async function loadTasks(listId: string,after?: string) {
    const token=++taskGeneration.current;setTaskLoading(true);setTaskCursor(null);setError('');
    try {
      const result=await api<Page<Task>>(`/todos/lists/${listId}/tasks`,{params:{after}});
      if(token===taskGeneration.current) {setTasks(result.items);setTaskCursor(result.next_cursor);return true;}
      return false;
    } catch(e:any) {if(token===taskGeneration.current) failed(e);return false;}
    finally{if(token===taskGeneration.current)setTaskLoading(false);}
  }
  useEffect(()=>{loadLists();return()=>{++generation.current;++taskGeneration.current;};},[ws?.id]);
  async function refreshShared() {
    const seen=updates.snapshot(), listId=selectedRef.current;
    // Refresh the visible cards in place, not page one: inserts or pagination
    // must never unmount a colleague's unsent comment or assignment choice.
    const visible=tasks.map(task=>task.id);
    if(!await loadLists())return;
    if(listId && selectedRef.current===listId) {
      if(visible.length===0) {if(!await loadTasks(listId))return;}
      else {
        const token=++taskGeneration.current;setTaskLoading(true);
        try {
          const rows=await Promise.all(visible.map(id=>api<Task>(`/todos/lists/${listId}/tasks/${id}`)));
          if(token!==taskGeneration.current || selectedRef.current!==listId)return;
          setTasks(rows);
        } catch(e:any) {if(token===taskGeneration.current)failed(e);return;}
        finally {if(token===taskGeneration.current)setTaskLoading(false);}
      }
    }
    updates.acknowledge(seen);
    setMessage('Displayed tasks checked. Refresh tasks to see new tasks or return to the first page. Refresh open comments separately.');
  }
  function choose(row:List) {selectedRef.current=row.id;++editorGeneration.current;++taskGeneration.current;setSelected(row);setRename(row.title);setRenameConflict(false);setTasks([]);setCreating(false);setEditing(null);loadTasks(row.id);}
  async function createList(event:FormEvent) {
    event.preventDefault();if(busy)return;setBusy(true);setError('');
    const creationGeneration=generation.current;
    try {
      listAttempt.current ??= {client_id:crypto.randomUUID(),title,workspace_id:ws?.id ?? null};
      const result=await api<List>('/todos/lists',{body:listAttempt.current});
      listAttempt.current=null;setUnconfirmed(false);setTitle('');
      if(creationGeneration!==generation.current)return;
      if(await loadLists()) {choose(result);setMessage('List saved.');}
    } catch(e:any) {failed(e);setUnconfirmed(uncertain(e));if(!uncertain(e)) listAttempt.current=null;} finally {setBusy(false);}
  }
  async function renameList(event:FormEvent) {
    event.preventDefault();if(busy||!selected)return;setBusy(true);setError('');
    const renameGeneration=generation.current, renameEditor=editorGeneration.current;
    try {
      const result=await api<List>(`/todos/lists/${selected.id}`,{method:'PUT',body:{title:rename,revision:selected.revision}});
      if(renameGeneration!==generation.current || renameEditor!==editorGeneration.current)return;
      setSelected(result);setLists(rows=>rows.map(r=>r.id===result.id?result:r));setRenameConflict(false);setMessage('List renamed.');
    } catch(e:any) {if(renameGeneration===generation.current && renameEditor===editorGeneration.current) {failed(e);setRenameConflict(e.status===409);}} finally {setBusy(false);}
  }
  async function latestList() {
    if(!selected)return;setBusy(true);setError('');
    const epoch=editorGeneration.current;
    try {
      const row=await api<List>(`/todos/lists/${selected.id}`);
      if(epoch!==editorGeneration.current)return;
      setSelected(row);setRename(row.title);setRenameConflict(false);setLists(rows=>rows.map(r=>r.id===row.id?row:r));
    } catch(e:any) {failed(e);} finally {setBusy(false);}
  }
  return <section className="todos">
    {ws ? <h2>To-do lists</h2> : <h1>My To-do Lists</h1>}
    <p className="notice">{ws ? `Shared with readers of ${ws.name}.` : 'Private to you. Administrators and colleagues cannot open these lists.'}</p>
    {ws && updates.pending && <div className="notice" role="status">
      Shared tasks or discussion may have changed. Refresh to check the latest saved work. Your drafts are kept.
      <button type="button" disabled={loading||taskLoading||busy} onClick={refreshShared}>Check shared updates</button>
    </div>}
    {!writable && <p>This workspace is read-only. You can read its tasks.</p>}
    <button type="button" onClick={()=>loadLists()}>Refresh lists</button>
    {error && <p className="error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {writable && <form onSubmit={createList}>
      <label>New list title<input required maxLength={200} disabled={busy||unconfirmed} value={title} onChange={e=>setTitle(e.target.value)} /></label>
      {unconfirmed && <p>List creation is unconfirmed. Retry the same request to recover it.</p>}
      <button type="submit" disabled={busy}>{unconfirmed?'Retry same list creation':'Create list'}</button>
    </form>}
    {loading ? <p role="status">Loading lists…</p> : lists.length===0 ? <p>No to-do lists in this scope yet.</p> : <nav aria-label="To-do lists"><ul>{lists.map(row=><li key={row.id}><button type="button" aria-pressed={selected?.id===row.id} disabled={busy} onClick={()=>choose(row)}>{row.title}</button></li>)}</ul></nav>}
    {listCursor && <button type="button" onClick={()=>loadLists(listCursor)}>More lists</button>}
    {selected && <section aria-label="Selected to-do list">
      <h3>{selected.title}</h3>
      {writable && <form onSubmit={renameList}><label>List name<input required maxLength={200} value={rename} onChange={e=>setRename(e.target.value)} /></label><button type="submit" disabled={busy}>Rename list</button></form>}
      {renameConflict && <p>Your list-name draft is kept. Loading the latest list will replace this draft.</p>}
      {renameConflict && writable && <button type="button" disabled={busy} onClick={latestList}>Load latest list (replaces draft)</button>}
      <button type="button" onClick={()=>loadTasks(selected.id)}>Refresh tasks</button>
      {writable && <button type="button" onClick={()=>{setCreating(true);setEditing(null);setEditorKey(++editorGeneration.current);}}>New task</button>}
      {taskLoading && <p role="status">Loading tasks…</p>}
      {!taskLoading && tasks.length===0 && <p>No tasks on this page.</p>}
      <ul className="todo-task-list">{tasks.map(task=><li className="card" key={task.id}>
        <h4>{task.done?'✓ ':''}{task.title}</h4><p>{workflowLabels[task.status] ?? (task.done?'Done':'To do')} · {task.priority} priority{task.due_date?` · Due ${task.due_date}`:''}</p>
        <p className="preserve">{task.description}</p>
        {task.checklist.length>0 && <ul>{task.checklist.map((item,i)=><li key={i}>{item.done?'✓':'○'} {item.title}</li>)}</ul>}
        <TaskAssignment listId={selected.id} taskId={task.id} revision={task.revision} assignee={task.assignee} writable={writable} saved={()=>{if(selectedRef.current===selected.id)loadTasks(selected.id);}} />
        <TaskComments listId={selected.id} taskId={task.id} writable={writable} workspaceId={ws?.id} />
        {task.has_source && <TaskSource listId={selected.id} taskId={task.id} />}
        <TaskHistory listId={selected.id} taskId={task.id} revision={task.revision} />
        {writable && <button type="button" onClick={()=>{setEditing(task);setCreating(false);setEditorKey(++editorGeneration.current);}}>Edit task: {task.title}</button>}
      </li>)}</ul>
      {taskCursor && <button type="button" onClick={()=>loadTasks(selected.id,taskCursor)}>More tasks</button>}
      {writable && (creating||editing) && <TaskEditor key={editorKey} listId={selected.id} initial={editing} cancel={()=>{++editorGeneration.current;setCreating(false);setEditing(null);}} saved={()=>{if(editorGeneration.current!==editorKey)return;++editorGeneration.current;setCreating(false);setEditing(null);setMessage('Task saved.');loadTasks(selected.id);}} />}
    </section>}
  </section>;
}
