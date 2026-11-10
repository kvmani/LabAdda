import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { useWorkspaces } from '../workspaces';

type Task = {id:string;list_id:string;list_title:string;workspace_id:string|null;title:string;description:string;status:string;due_date:string|null;priority:string};
type Page = {items:Task[];next_cursor:string|null;restart_required:boolean};
const states: Record<string,string>={todo:'To do',in_progress:'In progress',blocked:'Blocked',done:'Done'};
export function MyTasks() {
  const {workspaces}=useWorkspaces();
  const visibility=workspaces.map(w=>w.id).sort().join('|');
  const [state,setState]=useState(''),[page,setPage]=useState<Page|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const generation=useRef(0);
  async function load(after?:string) {
    const token=++generation.current;setPage(null);setError('');setLoading(true);
    try {
      const result=await api<Page>('/todos/mine',{params:{status:state,after}});
      if(token===generation.current)setPage(result);
    }catch(e:any){if(token===generation.current)setError(e.message);}
    finally{if(token===generation.current)setLoading(false);}
  }
  useEffect(()=>{load();return()=>{++generation.current;};},[state,visibility]);
  return <section className="todos"><h1>My Tasks</h1>
    <p>Your personal tasks and shared tasks assigned to you in spaces you can currently access.</p>
    <label>My Tasks state<select aria-label="My Tasks state" value={state} onChange={e=>{++generation.current;setPage(null);setState(e.target.value);}}><option value="">All states</option>{Object.entries(states).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <button type="button" onClick={()=>load()} disabled={loading}>Refresh My Tasks</button>
    {loading && <p role="status">Loading My Tasks…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {page && <>
      {page.restart_required && <p role="status">Access changed while loading. Refresh My Tasks to start again.</p>}
      {page.items.length===0 && <p>No personal or assigned tasks match this filter.</p>}
      <ul className="todo-task-list">{page.items.map(task=><li key={task.id} className="card">
        <h2>{task.title}</h2><p>{states[task.status]} · {task.priority} priority{task.due_date?` · Due ${task.due_date}`:''}</p>
        <p>{task.description.slice(0,200)}{task.description.length>200?'…':''}</p>
        <p>{task.workspace_id ? workspaces.find(w=>w.id===task.workspace_id)?.name ?? 'Shared workspace' : 'Private list'} · {task.list_title}</p>
        <Link to={task.workspace_id?`/w/${task.workspace_id}/todos`:'/todos'}>Open list: {task.list_title}</Link>
      </li>)}</ul>
      {page.next_cursor && <button type="button" onClick={()=>load(page.next_cursor!)}>More My Tasks</button>}
    </>}
  </section>;
}
