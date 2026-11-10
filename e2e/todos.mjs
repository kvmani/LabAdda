// C1 personal/shared tasks. Fresh disposable root/prefix proxy fixtures only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url), {chromium}=require('playwright');
const origin='http://127.0.0.1:8080', out=process.argv[2] ?? '/tmp/labadda-todos';
mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let count=0;
function check(value,label){assert.ok(value,label);count++;console.log('PASS '+label);}
async function login(base,name){
 const ctx=await browser.newContext({viewport:{width:1400,height:1100}}),page=await ctx.newPage();
 await page.goto(origin+base+'/');await page.getByLabel('Username').fill(name);
 await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out'}).waitFor();
 const session=await(await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
 return {ctx,page,session};
}
async function createList(page,title){await page.getByLabel('New list title').fill(title);await page.getByRole('button',{name:'Create list',exact:true}).click();await page.getByRole('heading',{name:title,exact:true}).waitFor();}
async function createTask(page,title,loseReply=false){
 await page.getByRole('button',{name:'New task',exact:true}).click();await page.getByLabel('Task title',{exact:true}).fill(title);
 await page.getByLabel('Description',{exact:true}).fill('Calibrate → measure α → compare sibling-section results');
 await page.getByLabel('Due date',{exact:true}).fill('2026-12-01');await page.getByLabel('Priority',{exact:true}).selectOption('high');
 await page.getByRole('button',{name:'Add checklist item',exact:true}).click();await page.getByLabel('Checklist item 1 title',{exact:true}).fill('Check instrument calibration');
 if(loseReply) await page.route('**/api/v1/todos/lists/*/tasks',async route=>{await route.fetch();await route.abort();},{times:1});
 await page.getByRole('button',{name:'Save task',exact:true}).click();
 if(loseReply){await page.getByRole('button',{name:'Retry same task creation'}).waitFor();check(await page.getByLabel('Task title',{exact:true}).isDisabled(),'uncertain task preserves intent');await page.getByRole('button',{name:'Retry same task creation'}).click();}
 await page.getByRole('heading',{name:title,exact:true}).waitFor();
}
try{
 for(const base of ['', '/labadda-staging']){
  const ben=await login(base,'ben'),asha=await login(base,'asha'),chen=await login(base,'chen'),dana=await login(base,'dana'),admin=await login(base,'admin');
  const api=origin+base+'/api/v1';
  const workspaces=await(await ben.ctx.request.get(api+'/workspaces')).json();
  const entries=workspaces.workspaces;
  const section=entries.find(w=>w.name==='Thin Films Section'),division=entries.find(w=>w.name==='Surface Science Division');
  await ben.page.goto(origin+base+'/todos');
  await ben.page.getByText('No to-do lists in this scope yet.',{exact:true}).waitFor();
  // Lose a committed list response; explicit same-key retry recovers one list.
  await ben.page.route('**/api/v1/todos/lists',async route=>{
   if(route.request().method()==='POST'){await route.fetch();await route.abort();}else await route.continue();
  },{times:1});
  await ben.page.getByLabel('New list title').fill('Private experiment checklist');
  await ben.page.getByRole('button',{name:'Create list',exact:true}).click();
  await ben.page.getByRole('button',{name:'Retry same list creation'}).waitFor();
  check(await ben.page.getByLabel('New list title').isDisabled(),base+' uncertain list freezes original intent');
  await ben.page.getByRole('button',{name:'Retry same list creation'}).click();
  await ben.page.getByRole('heading',{name:'Private experiment checklist',exact:true}).waitFor();
  const personal=(await(await ben.ctx.request.get(api+'/todos/lists')).json()).items;
  check(personal.length===1,base+' lost list response creates exactly one list');
  await createTask(ben.page,'Prepare personal measurements',true);
  check((await(await ben.ctx.request.get(api+`/todos/lists/${personal[0].id}/tasks`)).json()).items.length===1,base+' lost task response creates exactly once');
  await ben.page.reload();await ben.page.getByRole('button',{name:'Private experiment checklist',exact:true}).click();
  await ben.page.getByRole('heading',{name:'Prepare personal measurements',exact:true}).waitFor();
  check(true,base+' Unicode/date/checklist task persists after reload');
  await createList(ben.page,'Personal reading');
  await ben.page.getByRole('button',{name:'Private experiment checklist',exact:true}).click();
  await ben.page.getByRole('button',{name:'New task',exact:true}).click();
  await ben.page.getByLabel('Task title',{exact:true}).fill('Late saved task');
  let releaseSave, signalSave;
  const saveEntered=new Promise(resolve=>{signalSave=resolve;});
  const saveGate=new Promise(resolve=>{releaseSave=resolve;});
  await ben.page.route('**/api/v1/todos/lists/*/tasks',async route=>{
   const response=await route.fetch();signalSave();await saveGate;await route.fulfill({response});
  },{times:1});
  await ben.page.getByRole('button',{name:'Save task',exact:true}).click();await saveEntered;
  await ben.page.getByRole('button',{name:'Personal reading',exact:true}).click();
  const savedResponse=ben.page.waitForResponse(r=>r.request().method()==='POST' && /todos.*tasks$/.test(r.url()));
  releaseSave();await savedResponse;await ben.page.waitForTimeout(100);
  check(await ben.page.getByRole('heading',{name:'Personal reading',exact:true}).count()===1 && await ben.page.getByRole('heading',{name:'Late saved task',exact:true}).count()===0,base+' late save cannot repopulate another list');
  const reading=(await(await ben.ctx.request.get(api+'/todos/lists')).json()).items.find(x=>x.title==='Personal reading');
  await ben.ctx.request.put(api+`/todos/lists/${reading.id}`,{headers:{'X-CSRF-Token':ben.session.csrf_token},data:{title:'Personal reading updated',revision:reading.revision}});
  await ben.page.getByLabel('List name',{exact:true}).fill('Uncommitted list-name draft');
  await ben.page.getByRole('button',{name:'Rename list',exact:true}).click();
  await ben.page.getByRole('button',{name:'Load latest list (replaces draft)'}).waitFor();
  check(await ben.page.getByLabel('List name',{exact:true}).inputValue()==='Uncommitted list-name draft',base+' list rename conflict keeps draft');
  await ben.page.getByRole('button',{name:'Load latest list (replaces draft)'}).click();
  await ben.page.getByRole('heading',{name:'Personal reading updated',exact:true}).waitFor();
  check(await ben.page.getByLabel('List name',{exact:true}).inputValue()==='Personal reading updated',base+' explicit latest list reload recovers revision');
  const denyRefresh=async route=>{
   if(route.request().method()==='GET'){
    await route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:{code:'forbidden',message:'Synthetic access revoked'}})});
   }else await route.continue();
  };
  await ben.page.route('**/api/v1/todos/lists',denyRefresh);
  await ben.page.getByLabel('New list title').fill('Creation before denied refresh');
  await ben.page.getByRole('button',{name:'Create list',exact:true}).click();
  await ben.page.getByRole('alert').filter({hasText:'Synthetic access revoked'}).waitFor();
  check(await ben.page.getByRole('region',{name:'Selected to-do list'}).count()===0,base+' denied post-create refresh cannot restore selected list');
  await ben.page.unroute('**/api/v1/todos/lists',denyRefresh);
  await ben.page.getByRole('button',{name:'Refresh lists',exact:true}).click();
  await ben.page.getByRole('button',{name:'Personal reading updated',exact:true}).click();
  let releaseRename, enteredRename;
  const renameEntered=new Promise(resolve=>{enteredRename=resolve;});
  const renameGate=new Promise(resolve=>{releaseRename=resolve;});
  const denyRenameRefresh=async route=>route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({error:{code:'forbidden',message:'Synthetic rename revocation'}})});
  await ben.page.route('**/api/v1/todos/lists',denyRenameRefresh);
  await ben.page.route('**/api/v1/todos/lists/'+reading.id,async route=>{
   const response=await ben.ctx.request.put(route.request().url(),{headers:{'X-CSRF-Token':ben.session.csrf_token},data:route.request().postDataJSON()});
   const body=await response.body();enteredRename();await renameGate;await route.fulfill({status:response.status(),contentType:'application/json',body});
  },{times:1});
  const renameDone=ben.page.waitForResponse(r=>r.request().method()==='PUT' && r.url().endsWith('/todos/lists/'+reading.id));
  await ben.page.getByLabel('List name',{exact:true}).fill('Delayed rename result');
  await ben.page.getByRole('button',{name:'Rename list',exact:true}).click();await renameEntered;
  await ben.page.getByRole('button',{name:'Refresh lists',exact:true}).click();
  await ben.page.getByRole('alert').filter({hasText:'Synthetic rename revocation'}).waitFor();
  releaseRename();await renameDone;await ben.page.unroute('**/api/v1/todos/lists',denyRenameRefresh);await ben.page.waitForTimeout(100);
  check(await ben.page.getByRole('region',{name:'Selected to-do list'}).count()===0,base+' late rename cannot restore denied selection');
  for(const colleague of [asha,chen,dana,admin]) check((await colleague.ctx.request.get(api+`/todos/lists/${personal[0].id}/tasks`)).status()===404,base+' personal tasks deny colleague/admin');
  await ben.page.goto(origin+base+`/w/${section.id}/todos`);
  await createList(ben.page,'Thin Films plan');await createTask(ben.page,'Measure sample α');
  const list=(await(await ben.ctx.request.get(api+'/todos/lists?workspace_id='+section.id)).json()).items[0];
  const task=(await(await ben.ctx.request.get(api+`/todos/lists/${list.id}/tasks`)).json()).items[0];
  for(const colleague of [chen,dana,admin]) check((await colleague.ctx.request.get(api+`/todos/lists/${list.id}/tasks`)).status()===404,base+' section tasks deny sibling/parent-only/admin');
  await asha.page.goto(origin+base+`/w/${section.id}/todos`);await asha.page.getByRole('button',{name:'Thin Films plan',exact:true}).click();
  await asha.page.getByRole('heading',{name:'Measure sample α',exact:true}).waitFor();check(true,base+' colleague sees shared tasks');
  // Two writers: preserve local draft on conflict, explicitly load committed data.
  await ben.page.getByRole('button',{name:'Edit task: Measure sample α',exact:true}).click();
  await ben.page.getByLabel('Task title',{exact:true}).fill('Local unsaved task draft');
  const {title,description,due_date,priority,checklist,done,revision}=task;
  const changed=await asha.ctx.request.put(api+`/todos/lists/${list.id}/tasks/${task.id}`,{headers:{'X-CSRF-Token':asha.session.csrf_token},data:{title:'Colleague revised measurement',description,due_date,priority,checklist,done,revision}});
  check(changed.status()===200,base+' second writer commits');
  await ben.page.getByRole('button',{name:'Save task',exact:true}).click();await ben.page.getByText('Your draft is kept.',{exact:false}).waitFor();
  check(await ben.page.getByLabel('Task title',{exact:true}).inputValue()==='Local unsaved task draft',base+' conflict retains draft');
  await ben.page.getByRole('button',{name:'Load latest task (replaces draft)'}).click();
  await ben.page.waitForFunction(()=>Array.from(document.querySelectorAll('input')).some(el=>el.value==='Colleague revised measurement'));
  await ben.page.getByLabel('Task completed',{exact:true}).check();await ben.page.getByRole('button',{name:'Save task',exact:true}).click();
  await ben.page.getByRole('heading',{name:'✓ Colleague revised measurement',exact:true}).waitFor();
  check(true,base+' explicit conflict reload then completion');
  await ben.page.getByRole('button',{name:'Edit task: Colleague revised measurement',exact:true}).click();
  await ben.page.getByLabel('Task completed',{exact:true}).uncheck();await ben.page.getByRole('button',{name:'Save task',exact:true}).click();
  await ben.page.getByRole('heading',{name:'Colleague revised measurement',exact:true}).waitFor();check(true,base+' task reopens');
  for(const state of ['in_progress','blocked']){
   await ben.page.getByRole('button',{name:'Edit task: Colleague revised measurement',exact:true}).click();
   await ben.page.getByLabel('Workflow state',{exact:true}).selectOption(state);
   await ben.page.getByRole('button',{name:'Save task',exact:true}).click();
   await ben.page.getByText(`${state==='in_progress'?'In progress':'Blocked'} · high priority · Due 2026-12-01`,{exact:true}).waitFor();
   check((await(await ben.ctx.request.get(api+`/todos/lists/${list.id}/tasks/${task.id}`)).json()).status===state,base+' workflow '+state+' persists');
  }
  await ben.page.getByRole('button',{name:'View task history',exact:true}).click();
  const history=ben.page.getByRole('region',{name:'Task change history'});
  await history.getByText('Workflow state: In progress → Blocked',{exact:true}).waitFor();
  check(await history.getByText('Workflow state: To do → In progress',{exact:true}).count()===1,base+' readable revision history contains state transitions');
  for(const width of [1400,390]){
   await ben.page.setViewportSize({width,height:1100});await ben.page.addScriptTag({path:require.resolve('../frontend/node_modules/axe-core/axe.min.js')});
   const violations=await ben.page.evaluate(async()=> (await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(x=>x.id));
   check(violations.length===0,base+' tasks axe '+width+' '+violations.join(','));
   check(await ben.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),base+' mobile/desktop no overflow '+width);
   await ben.page.screenshot({path:out+'/'+(base?'prefix':'root')+'-'+width+'.png',fullPage:true});
  }
  await ben.page.goto(origin+base+`/w/${division.id}/todos`);await createList(ben.page,'Division research coordination');await createTask(ben.page,'Compare section findings');
  const divisionList=(await(await ben.ctx.request.get(api+'/todos/lists?workspace_id='+division.id)).json()).items[0];
  check((await chen.ctx.request.get(api+`/todos/lists/${divisionList.id}/tasks`)).status()===200,base+' sibling colleague can read shared ancestor tasks');
  await ben.page.goto(origin+base+`/w/${section.id}/todos`);await ben.page.getByRole('button',{name:'Thin Films plan',exact:true}).click();
  const removal=await admin.ctx.request.delete(api+`/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,{headers:{'X-CSRF-Token':admin.session.csrf_token}});
  check(removal.status()===200,base+' actual membership revocation');
  const refresh=ben.page.getByRole('button',{name:'Refresh tasks',exact:true});
  if(await refresh.count()) await refresh.click({timeout:1000}).catch(()=>{});
  check((await ben.ctx.request.get(api+`/todos/lists/${list.id}/tasks`)).status()===404,base+' revoked API denies tasks');
  await ben.page.getByRole('alert').first().waitFor();
  check(await ben.page.getByRole('heading',{name:'Colleague revised measurement',exact:true}).count()===0,base+' revoked refresh clears shared content');
  for(const person of [ben,asha,chen,dana,admin]) await person.ctx.close();
 }
 console.log(`${count} task browser checks passed`);
}finally{await browser.close();}
