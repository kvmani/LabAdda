// Fresh screenshots of current features on the existing, synthetic research demo.
// Additive fixture: never resets data or grants. Requires the research-day scenario.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
const {chromium}=createRequire(import.meta.url)('playwright');
const origin=process.argv[2] ?? 'http://127.0.0.1:8010';
const out=resolve(process.argv[3] ?? '/workspace/artifacts/collaboration-review-2026-11-10');
if(process.argv[4]!=='--synthetic-instance' || !['localhost','127.0.0.1'].includes(new URL(origin).hostname))throw Error('Use an explicitly synthetic local instance');
mkdirSync(out,{recursive:true});
const names=['asha','ben','mira','chen','dana'];
const objects=JSON.parse(readFileSync(new URL('../fixtures/research-day/board-objects.json',import.meta.url)));
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
const actors={},shots=[],checks=[],errors=[];
function check(value,label){assert.ok(value,label);checks.push(label);console.log('PASS '+label);}
async function call(a,path,body,method=body===undefined?'GET':'POST'){
 const response=await a.ctx.request.fetch(origin+'/api/v1'+path,{method,headers:{'X-CSRF-Token':a.csrf},data:body});
 assert.ok(response.ok(),`${method} ${path}: ${response.status()} ${await response.text()}`);return response.json();
}
async function photo(a,file,caption,fullPage=false){await a.page.screenshot({path:out+'/'+file,fullPage});shots.push({file,caption,actor:a.name});}
async function go(a,id,tab){await a.page.goto(origin+`/w/${id}/${tab}`);await a.page.getByRole('heading',{level:1}).waitFor();}
async function list(a,workspace,title){
 const existing=(await call(a,'/todos/lists?limit=50'+(workspace?'&workspace_id='+workspace:''))).items.find(r=>r.title===title);
 return existing ?? call(a,'/todos/lists',{client_id:crypto.randomUUID(),title,workspace_id:workspace});
}
async function task(a,l,spec){
 let record=(await call(a,`/todos/lists/${l.id}/tasks?limit=50`)).items.find(r=>r.title===spec.title);
 if(!record){
  const {owner,...fields}=spec;record=await call(a,`/todos/lists/${l.id}/tasks`,{client_id:crypto.randomUUID(),...fields});
  if(owner)record=await call(a,`/todos/lists/${l.id}/tasks/${record.id}/assignee`,{user_id:actors[owner].id,revision:record.revision},'PUT');
 }
 return record;
}
try{
 for(const name of names){
  const ctx=await browser.newContext({viewport:{width:1600,height:1120},timezoneId:'Asia/Kolkata'}),page=await ctx.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(origin)&&!r.url().startsWith('data:'))errors.push('External request');});
  await page.goto(origin);await page.getByLabel('Username').fill(name);await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out'}).waitFor();
  const session=await(await ctx.request.get(origin+'/api/v1/auth/session')).json();actors[name]={name,ctx,page,csrf:session.csrf_token,id:session.user.id};
 }
 const {ben,asha,mira,chen,dana}=actors;
 const spaces=(await call(ben,'/workspaces')).workspaces;
 const group=spaces.find(w=>w.name==='Aurora - interface study');assert.ok(group,'Existing research-day group is required; no reset is performed');
 const board=await call(ben,`/workspaces/${group.id}/board`);check(board.revision>=663,'Existing handwritten research plan preserved');
 for(const a of Object.values(actors))await go(a,group.id,'board');
 // Each participant contributes a fresh native ink mark without replacing old work.
 for(let i=0;i<names.length;i++){
  const a=actors[names[i]],x=55+i*188;
  await call(a,`/workspaces/${group.id}/board/ops`,{epoch:board.epoch,type:'add',op_id:'review-20261110-ink-'+a.name,object_id:'review-20261110-mark-'+a.name,payload:{kind:'stroke',data:{points:[[x,687],[x+50,689],[x+100,687]],color:['#c62828','#1565c0','#2e7d32','#ef6c00','#6a1b9a'][i],width:2}}});
 }
 const conversation=[
  ['asha','Project idea: compare 20, 40 and 60 nm films to test whether interface vacancies drive the catalytic change. I will keep an uncoated witness for every batch.'],
  ['chen','Let us add a blank and reference between batches. My GC task is blocked until the reference drift is checked; three replicates will help separate noise from an interface effect.'],
  ['mira','I can take the XPS surface checks. Please log transfer time and keep an inert cap: air exposure could mimic the vacancy signal.'],
  ['ben','I have mapped sample IDs to runs and assigned the followups. The shared board records the plan; my private scratchpad keeps the checks I want to finish before the review.'],
  ['dana','Decision gate: agree controls first, then compare uncertainty across the two sections. Bring only the reviewed interpretation to the division meeting.']
 ];
 for(const [i,[name,body]] of conversation.entries())await call(actors[name],`/workspaces/${group.id}/chat`,{client_id:'review-20261110-chat-'+i,body});
 for(const a of Object.values(actors)){
  await a.page.getByRole('button',{name:'Fit',exact:true}).click();await a.page.getByText('Saved',{exact:true}).waitFor();
  await a.page.getByText(/5 here:/).waitFor();
 }
 check(true,'Five authenticated researchers share one live whiteboard');
 for(const name of names)await photo(actors[name],'board-'+name+'.png',actors[name].name+': five-person project whiteboard with native handwritten plan and stickies');
 await go(chen,group.id,'chat');await chen.page.getByText(conversation.at(-1)[1],{exact:true}).waitFor();
 await photo(chen,'shared-discussion.png','Shared project chat: five roles, controls, uncertainty and a division decision gate');
 const shared=await list(ben,group.id,'Aurora idea sprint · review 2026-11-10');
 const specs=[
  {title:'Prepare 20 / 40 / 60 nm film series',description:'Retain an uncoated witness coupon for each deposition. Label transfer boxes before the cross-section handoff.',due_date:'2026-11-12',priority:'high',status:'in_progress',done:false,checklist:[{title:'Reserve deposition slot',done:true},{title:'Prepare and label witness coupons',done:false}],owner:'asha'},
  {title:'Repeat GC reference and three replicates',description:'Blocked until the 40 nm reference drift is checked. Compare blank, reference and sample under the same sequence.',due_date:'2026-11-13',priority:'high',status:'blocked',done:false,checklist:[{title:'Confirm instrument slot',done:true},{title:'Resolve reference drift',done:false}],owner:'chen'},
  {title:'Measure XPS surface state after capped transfer',description:'Record air exposure and transfer time so the vacancy interpretation has a defensible control.',due_date:'2026-11-13',priority:'normal',status:'todo',done:false,checklist:[{title:'Prepare inert sample caps',done:false}],owner:'mira'},
  {title:'Review controls before the go / no-go decision',description:'Compare both sections at division level. Decide on the next deposition batch only after reviewing uncertainty.',due_date:'2026-11-16',priority:'normal',status:'todo',done:false,checklist:[{title:'Collect section summaries',done:false}],owner:'dana'},
  {title:'Reconcile sample-to-run mapping',description:'The shared sample/run table has been checked against the board plan.',due_date:'2026-11-12',priority:'normal',status:'done',done:true,checklist:[{title:'Match all sample and run IDs',done:true}],owner:'ben'}
 ];
 const work=[];for(const spec of specs)work.push(await task(ben,shared,spec));
 const first=work[0];
 for(const [i,name] of names.entries()){
  const text=['Preparation controls are on the board. I will retain a witness coupon.','Sample-to-run mapping is complete; the private drift check stays separate.','Please record the capped transfer time with each XPS run.','GC blanks are ready; reference drift is the blocking item.','Review the controls before promoting conclusions to the division.'][i];
  const existing=(await call(actors[name],`/todos/lists/${shared.id}/tasks/${first.id}/comments`)).items;
  if(!existing.some(r=>r.body===text&&r.author.id===actors[name].id))await call(actors[name],`/todos/lists/${shared.id}/tasks/${first.id}/comments`,{client_id:crypto.randomUUID(),body:text});
 }
 await go(ben,group.id,'todos');await ben.page.getByRole('button',{name:shared.title,exact:true}).click();await ben.page.getByRole('heading',{name:specs[0].title,exact:true}).waitFor();
 await photo(ben,'shared-tasks.png','Shared sprint: five named assignees, due dates, priorities, checklists and workflow states',true);
 const card=ben.page.locator('.todo-task-list > li').filter({has:ben.page.getByRole('heading',{name:first.title,exact:true})});
 await card.getByRole('button',{name:'View comments',exact:true}).click();await card.getByText('Preparation controls are on the board. I will retain a witness coupon.',{exact:true}).waitFor();
 await card.scrollIntoViewIfNeeded();await photo(ben,'task-discussion.png','Task discussion: all five researchers contribute to the preparation decision',true);
 const personal=await list(ben,null,'Private planning · Aurora review');
 await task(ben,personal,{title:'Check reference drift before sharing a conclusion',description:'Repeat the 40 nm reference and note the uncertainty. This is a private followup, not a group conclusion.',due_date:'2026-11-12',priority:'high',status:'in_progress',done:false,checklist:[{title:'Compare yesterday’s reference',done:true},{title:'Repeat measurement',done:false}]});
 await task(ben,personal,{title:'Prepare questions for Mira',description:'Ask about transfer-time sensitivity and an independent surface control.',due_date:'2026-11-13',priority:'normal',status:'todo',done:false,checklist:[]});
 await ben.page.goto(origin+'/todos');await ben.page.getByRole('button',{name:personal.title,exact:true}).click();await ben.page.getByRole('heading',{name:'Check reference drift before sharing a conclusion',exact:true}).waitFor();
 await photo(ben,'personal-todos.png','Ben: private planning lists and personal followups',true);
 await ben.page.goto(origin+'/my-tasks');await ben.page.getByRole('heading',{name:'My Tasks',exact:true}).waitFor();await ben.page.getByRole('heading',{name:'Reconcile sample-to-run mapping',exact:true}).waitFor();
 await photo(ben,'my-tasks.png','Ben: personal work and assigned shared work in My Tasks',true);
 const notes=await call(ben,'/notes');let note=notes.notes.find(n=>n.title==='Private idea — before group review');
 if(!note)note=await call(ben,'/notes',{title:'Private idea — before group review',body:'Hypothesis to check: is the apparent vacancy effect actually reference drift?\n\nBefore the meeting:\n• Repeat the 40 nm reference.\n• Ask Mira about capped transfer.\n• Keep uncertainty separate from the draft conclusion.'});
 await ben.page.goto(origin+'/notes');await ben.page.getByRole('heading',{name:note.title,exact:true}).waitFor();await photo(ben,'personal-notes.png','Ben: dedicated My Notes, owner-only text and reminders',true);
 let scratch=(await call(ben,'/workspaces')).workspaces.find(w=>w.name==='Ben - private idea scratchpad (review)');
 if(!scratch)scratch=await call(ben,'/groups',{name:'Ben - private idea scratchpad (review)',description:'Synthetic owner-only scratchpad. No colleagues invited.',member_ids:[]});
 const scratchBoard=await call(ben,`/workspaces/${scratch.id}/board`);
 let ink=0;
 for(const [i,source] of [objects[1],objects[0],objects[2]].entries()){
  const x=50+i*230,y=60,dx=x-source.data.x,dy=y-source.data.y;
  await call(ben,`/workspaces/${scratch.id}/board/ops`,{epoch:scratchBoard.epoch,type:'add',op_id:'review-private-sticky-'+i,object_id:'review-private-sticky-'+i,payload:{kind:'sticky',data:{...source.data,x,y,text:['PRIVATE / CHECK','NEXT / PREP','ASK / MIRA'][i]}}});
  const strokes=objects.filter(o=>o.kind==='stroke'&&o.actor===source.actor&&o.data.points.every(p=>p[0]>=source.data.x&&p[0]<=source.data.x+180&&p[1]>=source.data.y+22&&p[1]<=source.data.y+120));
  for(const [j,stroke] of strokes.entries()){
   await call(ben,`/workspaces/${scratch.id}/board/ops`,{epoch:scratchBoard.epoch,type:'add',op_id:`review-private-ink-${i}-${j}`,object_id:`review-private-ink-${i}-${j}`,payload:{kind:'stroke',data:{...stroke.data,points:stroke.data.points.map(([a,b])=>[a+dx,b+dy])}}});ink++;
  }
 }
 await go(ben,scratch.id,'board');await ben.page.getByRole('button',{name:'Fit',exact:true}).click();await ben.page.getByText('Saved',{exact:true}).waitFor();await photo(ben,'personal-stickies.png','Ben: personal handwritten stickies in an owner-only group board (not a dedicated personal-board feature)');
 for(const a of [asha,mira,chen,dana]){
  assert.equal((await a.ctx.request.get(origin+`/api/v1/notes/${note.id}`)).status(),404);
  assert.equal((await a.ctx.request.get(origin+`/api/v1/todos/lists/${personal.id}/tasks`)).status(),404);
  assert.equal((await a.ctx.request.get(origin+`/api/v1/workspaces/${scratch.id}/board`)).status(),404);
 }
 check(ink>0,'Private scratchpad uses actual native handwriting, with only its owner admitted');
 check(true,'Colleagues cannot retrieve the personal notes, tasks or scratchpad');
 check(errors.length===0,'No browser errors or external assets');
 const escape=s=>s.replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 writeFileSync(out+'/index.html',`<!doctype html><meta charset="utf-8"><title>LabAdda collaboration review</title><style>body{font:16px system-ui;background:#edf1f5;color:#173042;margin:24px auto;max-width:1500px;padding:0 16px}article{background:white;padding:20px;margin:28px 0;border-radius:12px}img{width:100%;height:auto}h1,h2{line-height:1.3}</style><h1>LabAdda — five-person project review</h1><p>Fresh screenshots of the running app. Synthetic research scenario: Asha and Ben (Thin Films), Chen and Mira (Catalysis), Dana (division). All five collaborate in the Aurora group. Private stickies use an owner-only group; dedicated My Notes and personal to-do lists are private features. Task/comment changes currently use refresh, not live task events.</p>${shots.map(s=>`<article><h2>${escape(s.caption)}</h2><a href="${s.file}"><img loading="lazy" src="${s.file}" alt="${escape(s.caption)}"></a></article>`).join('')}`);
 writeFileSync(out+'/report.json',JSON.stringify({origin,checks,shots,shared_group:group.id,private_scratchpad:scratch.id,handwritten_private_strokes:ink},null,2));
 console.log(`${shots.length} screenshots captured at ${out}`);
}finally{for(const a of Object.values(actors))await a.ctx.close();await browser.close();}
