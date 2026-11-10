import {useEffect,useRef,useState,type FormEvent} from 'react';
import {api,newId} from '../api';
import type {ChatMessage,Workspace} from '../types';

type Intent={body:string;client_id:string;parent_id:string|null};
export function ChatComposer({ws,parentId=null,sent,denied}:{ws:Workspace;parentId?:string|null;sent:(message:ChatMessage)=>void;denied:()=>void}){
 const [text,setText]=useState(''),[busy,setBusy]=useState(false),[unknown,setUnknown]=useState(false),[error,setError]=useState('');
 const attempt=useRef<Intent|null>(null),generation=useRef(0);
 useEffect(()=>()=>{++generation.current;},[ws.id,parentId]);
 async function submit(event:FormEvent){
  event.preventDefault();if(busy||!ws.can_write||!text.trim())return;
  const token=++generation.current;setBusy(true);setError('');
  try{
   attempt.current??={body:text,client_id:newId('chat'),parent_id:parentId};
   const message=await api<ChatMessage>(`/workspaces/${ws.id}/chat`,{body:attempt.current});
   if(token!==generation.current)return;
   attempt.current=null;setUnknown(false);setText('');sent(message);
  }catch(e:any){if(token===generation.current){setError(e.message);const uncertain=e.status===0||e.status>=500;setUnknown(uncertain);if(!uncertain)attempt.current=null;if([401,403,404].includes(e.status))denied();}}
  finally{if(token===generation.current)setBusy(false);}
 }
 if(!ws.can_write)return <p className="notice">Chat is read-only here.</p>;
 return <form onSubmit={submit} aria-label={parentId?'Reply to thread':'Send chat message'}>
  <label>{parentId?'Thread reply':`Message ${ws.name}`}<input aria-label={parentId?'Thread reply':`Message ${ws.name}`} value={text} maxLength={4000} disabled={busy||unknown} onChange={e=>setText(e.target.value)} /></label>
  {error&&<p className="error" role="alert">{error}</p>}
  {unknown&&<p role="status">Message outcome is unconfirmed. Retry the same message; its text and thread are kept unchanged.</p>}
  <button type="submit" disabled={busy}>{busy?'Sending…':unknown?'Retry same message':parentId?'Send reply':'Send'}</button>
 </form>;
}
