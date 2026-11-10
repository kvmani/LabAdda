import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { realtime } from '../realtime';
import { useWorkspaces } from '../workspaces';
import type { Workspace } from '../types';

type List = {id:string;title:string};
type Page = {items:List[];next_cursor:string|null};
type Intent = {listId:string;body:{client_id:string;title:string;description:string;source_kind:'post'|'chat';source_id:string;confirm_audience:boolean}};

/** The user reviews a copy. Source references never broaden source permissions. */
export function ConversationTask({source,kind,sourceId,text,close}:{source:Workspace;kind:'post'|'chat';sourceId:string;text:string;close:()=>void}) {
  const {workspaces}=useWorkspaces();
  const [destination,setDestination]=useState(source.can_write&&!source.archived?source.id:'personal');
  const [lists,setLists]=useState<Page|null>(null),[listId,setListId]=useState('');
  const [title,setTitle]=useState(text.trim().split('\n')[0].slice(0,200)),[description,setDescription]=useState(text.slice(0,10000));
  const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[loading,setLoading]=useState(false);
  const [unknown,setUnknown]=useState(false),[blocked,setBlocked]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
  const generation=useRef(0),attempt=useRef<Intent|null>(null);
  const target=workspaces.find(w=>w.id===destination), broader=destination!=='personal'&&destination!==source.id;
  const writable=destination==='personal'||!!target?.can_write&&!target.archived;
  const location=destination==='personal'?'/todos':`/w/${destination}/todos`;
  function deny(){++generation.current;setBlocked(true);setTitle('');setDescription('');setLists(null);setListId('');attempt.current=null;setBusy(false);setLoading(false);setUnknown(false);}
  useEffect(()=>{
    let active=true;
    const unsubs=[...new Set([source.id,...(destination==='personal'?[]:[destination])])].map(id=>realtime.subscribe(id,event=>{
      if(active&&['revoked','subscribe_failed','session_ended'].includes(event.type))deny();
    }));
    return()=>{active=false;++generation.current;unsubs.forEach(stop=>stop());};
  },[source.id,destination]);
  async function load(after?:string){
    const token=++generation.current;setLoading(true);setError('');
    try{
      const page=await api<Page>('/todos/lists',{params:{workspace_id:destination==='personal'?undefined:destination,after}});
      if(token===generation.current)setLists(page);
    }catch(e:any){if(token===generation.current){setError(e.message);if([401,403,404].includes(e.status))deny();}}
    finally{if(token===generation.current)setLoading(false);}
  }
  useEffect(()=>{setLists(null);setListId('');setConfirmed(false);load();},[destination]);
  async function submit(event:FormEvent){
    event.preventDefault();if(busy||blocked||saved||!writable||!listId||broader&&!confirmed)return;
    const token=++generation.current;setBusy(true);setError('');
    try{
      attempt.current ??= {listId,body:{client_id:crypto.randomUUID(),title,description,source_kind:kind,source_id:sourceId,confirm_audience:confirmed}};
      await api(`/todos/lists/${attempt.current.listId}/from-conversation`,{body:attempt.current.body});
      if(token!==generation.current)return;
      setSaved(true);setUnknown(false);attempt.current=null;
    }catch(e:any){if(token===generation.current){setError(e.message);const uncertain=e.status===0||e.status>=500;setUnknown(uncertain);if(!uncertain)attempt.current=null;if([401,403,404].includes(e.status))deny();}}
    finally{if(token===generation.current)setBusy(false);}
  }
  if(blocked)return <section className="card" aria-label="Create task from conversation"><p role="alert">The conversation or destination is no longer available. Reopen it after checking access.</p><button type="button" onClick={close}>Close task creation</button></section>;
  if(saved)return <section className="card" aria-label="Create task from conversation"><p role="status">Task saved. Its source link still requires access to the original conversation.</p><Link to={location}>Open destination tasks</Link><button type="button" onClick={close}>Close task creation</button></section>;
  return <form className="card conversation-task" aria-label="Create task from conversation" onSubmit={submit}>
    <h3>Create task from {kind==='post'?'post':'chat message'}</h3>
    <p>Review the copied text and destination before saving. Later conversation changes do not update this task copy.</p>
    <fieldset disabled={busy||unknown}>
      <label>Task destination<select aria-label="Task destination" value={destination} onChange={e=>{++generation.current;setDestination(e.target.value);setLists(null);setListId('');setConfirmed(false);}}>
        <option value="personal">My personal lists (private)</option>
        {workspaces.filter(w=>w.can_write&&!w.archived).map(w=><option key={w.id} value={w.id}>{w.name}</option>)}
      </select></label>
      <p className="notice">{destination==='personal'?'Audience: only you.':`Audience: everyone who can read ${target?.name ?? 'the selected workspace'}.`}</p>
      {loading&&<p role="status">Loading destination lists…</p>}
      {lists&&<label>Destination list<select aria-label="Destination list" required value={listId} onChange={e=>{setListId(e.target.value);setConfirmed(false);}}><option value="">Choose a list</option>{lists.items.map(row=><option key={row.id} value={row.id}>{row.title}</option>)}</select></label>}
      {lists?.items.length===0&&<p>Create a to-do list in the destination first, then reopen this form.</p>}
      <button type="button" disabled={loading} onClick={()=>{setListId('');setConfirmed(false);load();}}>Refresh destination lists</button>
      {lists?.next_cursor&&<button type="button" disabled={loading} onClick={()=>{setListId('');setConfirmed(false);load(lists.next_cursor!);}}>More destination lists</button>}
      <label>Task title<input required maxLength={200} value={title} onChange={e=>setTitle(e.target.value)} /></label>
      <label>Task description<textarea aria-label="Task description" maxLength={10000} value={description} onChange={e=>setDescription(e.target.value)} /></label>
      {broader&&<label className="warning"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />I confirm this reviewed task text will be shared with a different audience in {target?.name}.</label>}
    </fieldset>
    {error&&<p role="alert" className="error">{error}</p>}
    {unknown&&<p role="status">Creation is unconfirmed. Retry the same task copy; the original destination and text are kept unchanged.</p>}
    <button type="submit" disabled={busy||loading||blocked||!writable||!listId||broader&&!confirmed}>{busy?'Saving…':unknown?'Retry same task copy':'Save conversation task'}</button>
    <button type="button" disabled={busy} onClick={close}>Close task creation</button>
  </form>;
}
