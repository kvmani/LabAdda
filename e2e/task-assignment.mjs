// C2 assignment/My Tasks: fresh disposable root/prefix proxy fixtures only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url),{chromium}=require('playwright');
const origin='http://127.0.0.1:8080',out=process.argv[2] ?? '/tmp/labadda-assignment';
mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let count=0;
function check(value,label){assert.ok(value,label);count++;console.log('PASS '+label);}
async function login(base,name){
 const ctx=await browser.newContext({viewport:{width:1400,height:1100}}),page=await ctx.newPage();
 await page.goto(origin+base+'/');await page.getByLabel('Username').fill(name);await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out'}).waitFor();
 const session=await(await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
 return {ctx,page,session,api:origin+base+'/api/v1',headers:{'X-CSRF-Token':session.csrf_token}};
}
async function create(user,workspace,title){
 const response=await user.ctx.request.post(user.api+'/todos/lists',{headers:user.headers,data:{client_id:crypto.randomUUID(),title,workspace_id:workspace}});
 assert.equal(response.status(),201);const list=await response.json();
 const taskResponse=await user.ctx.request.post(user.api+`/todos/lists/${list.id}/tasks`,{headers:user.headers,data:{client_id:crypto.randomUUID(),title:title+' task'}});
 assert.equal(taskResponse.status(),201);return {list,task:await taskResponse.json()};
}
async function assign(user,record,id){
 const result=await user.ctx.request.put(user.api+`/todos/lists/${record.list.id}/tasks/${record.task.id}/assignee`,{headers:user.headers,data:{user_id:id,revision:record.task.revision}});
 assert.equal(result.status(),200);record.task=await result.json();
}
try{
 for(const base of ['', '/labadda-staging']){
  const ben=await login(base,'ben'),asha=await login(base,'asha'),chen=await login(base,'chen'),dana=await login(base,'dana'),admin=await login(base,'admin');
  const spaces=(await(await ben.ctx.request.get(ben.api+'/workspaces')).json()).workspaces;
  const section=spaces.find(w=>w.name==='Thin Films Section'),division=spaces.find(w=>w.name==='Surface Science Division'),group=spaces.find(w=>w.kind==='group');
  const shared=await create(ben,section.id,'Section responsibility'),personal=await create(ben,null,'Personal notebook');
  const div=await create(ben,division.id,'Division coordination'),team=await create(ben,group.id,'Reading club');
  await assign(ben,div,chen.session.user.id);await assign(ben,team,chen.session.user.id);
  await ben.page.goto(origin+base+`/w/${section.id}/todos`);
  await ben.page.getByRole('button',{name:shared.list.title,exact:true}).click();
  await ben.page.getByRole('button',{name:'Change assignee',exact:true}).click();
  await ben.page.getByLabel('Assignee',{exact:true}).waitFor();
  const options=await ben.page.getByLabel('Assignee',{exact:true}).locator('option').allTextContents();
  check(options.length===3 && options.some(x=>x.includes('Asha')) && !options.some(x=>/Chen|Dana|Administrator|Fay/.test(x)),base+' eligible picker excludes siblings/parent/admin/inactive');
  await ben.page.getByLabel('Assignee',{exact:true}).selectOption(asha.session.user.id);
  await ben.page.getByRole('button',{name:'Save assignment',exact:true}).click();
  await ben.page.getByText('Assignee: Asha Rao',{exact:true}).waitFor();check(true,base+' shared assignment persists in task view');
  await asha.page.goto(origin+base+'/my-tasks');await asha.page.getByRole('heading',{name:shared.task.title,exact:true}).waitFor();
  check(true,base+' assigned colleague sees My Tasks');
  await ben.page.goto(origin+base+'/my-tasks');await ben.page.getByRole('heading',{name:personal.task.title,exact:true}).waitFor();
  check(await ben.page.getByRole('heading',{name:shared.task.title,exact:true}).count()===0,base+' author is not implicitly assigned shared task');
  for(const outsider of [dana,admin]){
   await outsider.page.goto(origin+base+'/my-tasks');await outsider.page.getByText('No personal or assigned tasks match this filter.',{exact:true}).waitFor();
   check(true,base+' parent/admin My Tasks cannot reveal section tasks');
  }
  await chen.page.goto(origin+base+'/my-tasks');await chen.page.getByRole('heading',{name:team.task.title,exact:true}).waitFor();
  check(await chen.page.getByRole('heading',{name:div.task.title,exact:true}).count()===1,base+' group and ancestor assignments coexist');
  await asha.page.getByRole('link',{name:'Open list: '+shared.list.title,exact:true}).click();
  await asha.page.getByRole('button',{name:shared.list.title,exact:true}).click();
  await asha.page.getByRole('button',{name:'Edit task: '+shared.task.title,exact:true}).click();
  await asha.page.getByLabel('Task completed',{exact:true}).check();await asha.page.getByRole('button',{name:'Save task',exact:true}).click();
  await asha.page.getByRole('heading',{name:'✓ '+shared.task.title,exact:true}).waitFor();
  await asha.page.goto(origin+base+'/my-tasks');await asha.page.getByLabel('My Tasks state',{exact:true}).selectOption('done');
  await asha.page.getByRole('heading',{name:shared.task.title,exact:true}).waitFor();check(true,base+' task completion preserves assignment and state filter');
  await ben.page.goto(origin+base+`/w/${section.id}/todos`);await ben.page.getByRole('button',{name:shared.list.title,exact:true}).click();
  await ben.page.getByRole('button',{name:'Change assignee',exact:true}).click();await ben.page.getByLabel('Assignee',{exact:true}).selectOption(ben.session.user.id);
  await ben.page.route('**/api/v1/todos/lists/*/tasks/*/assignee',async route=>{await route.fetch();await route.abort();},{times:1});
  await ben.page.getByRole('button',{name:'Save assignment',exact:true}).click();
  await ben.page.getByRole('button',{name:'Reload task assignment',exact:true}).waitFor();
  check(await ben.page.getByRole('button',{name:'Save assignment',exact:true}).isDisabled(),base+' unknown assignment outcome blocks blind retry');
  await ben.page.getByRole('button',{name:'Reload task assignment',exact:true}).click();
  await ben.page.getByText('Assignee: Ben Okafor',{exact:true}).waitFor();check(true,base+' committed lost reply resolves through task reload');
  await ben.page.getByRole('button',{name:'Change assignee',exact:true}).click();await ben.page.getByLabel('Assignee',{exact:true}).selectOption(asha.session.user.id);
  const current=await(await ben.ctx.request.get(ben.api+`/todos/lists/${shared.list.id}/tasks/${shared.task.id}`)).json();
  const {title,description,due_date,priority,checklist,done,status,revision}=current;
  const changed=await asha.ctx.request.put(asha.api+`/todos/lists/${shared.list.id}/tasks/${shared.task.id}`,{headers:asha.headers,data:{title:'Colleague updated responsibility',description,due_date,priority,checklist,done,status,revision}});
  check(changed.status()===200,base+' concurrent task writer commits');
  await ben.page.getByRole('button',{name:'Save assignment',exact:true}).click();await ben.page.getByRole('button',{name:'Reload task assignment',exact:true}).waitFor();
  check(await ben.page.getByLabel('Assignee',{exact:true}).inputValue()===asha.session.user.id,base+' assignment conflict keeps chosen colleague');
  await ben.page.getByRole('button',{name:'Reload task assignment',exact:true}).click();
  await ben.page.getByRole('heading',{name:'✓ Colleague updated responsibility',exact:true}).waitFor();check(true,base+' conflict reload preserves committed task and assignment');
  await ben.page.goto(origin+base+'/my-tasks');await ben.page.getByRole('heading',{name:'Colleague updated responsibility',exact:true}).waitFor();
  const removed=await admin.ctx.request.delete(admin.api+`/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,{headers:admin.headers});
  check(removed.status()===200,base+' actual section membership removed');
  await ben.page.getByRole('button',{name:'Refresh My Tasks',exact:true}).click();
  await ben.page.getByRole('heading',{name:personal.task.title,exact:true}).waitFor();
  check(await ben.page.getByRole('heading',{name:'Colleague updated responsibility',exact:true}).count()===0,base+' revoked shared task hidden while personal remains');
  let release,entered;const gate=new Promise(resolve=>{release=resolve;}),started=new Promise(resolve=>{entered=resolve;});
  await ben.page.route('**/api/v1/todos/mine',async route=>{const response=await route.fetch();entered();await gate;await route.fulfill({response});},{times:1});
  await ben.page.getByRole('button',{name:'Refresh My Tasks',exact:true}).click();await started;
  await ben.page.getByLabel('My Tasks state',{exact:true}).selectOption('done');
  await ben.page.getByText('No personal or assigned tasks match this filter.',{exact:true}).waitFor();
  const finished=ben.page.waitForResponse(r=>r.url().endsWith('/todos/mine'));release();await finished;await ben.page.waitForTimeout(100);
  check(await ben.page.getByRole('heading',{name:personal.task.title,exact:true}).count()===0,base+' delayed dashboard response cannot override new filter');
  await ben.page.getByLabel('My Tasks state',{exact:true}).selectOption('');await ben.page.getByRole('heading',{name:personal.task.title,exact:true}).waitFor();
  for(const width of [1400,390]){
   await ben.page.setViewportSize({width,height:1100});await ben.page.addScriptTag({path:require.resolve('../frontend/node_modules/axe-core/axe.min.js')});
   const violations=await ben.page.evaluate(async()=> (await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id));
   check(violations.length===0,base+' My Tasks axe '+width+' '+violations.join(','));
   check(await ben.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),base+' My Tasks overflow '+width);
   await ben.page.screenshot({path:out+'/'+(base?'prefix':'root')+'-my-tasks-'+width+'.png',fullPage:true});
  }
  await ben.page.goto(origin+base+'/todos');await ben.page.getByRole('button',{name:personal.list.title,exact:true}).click();
  await ben.page.getByRole('button',{name:'Change assignee',exact:true}).click();await ben.page.getByLabel('Assignee',{exact:true}).waitFor();
  check((await ben.page.getByLabel('Assignee',{exact:true}).locator('option').allTextContents()).length===2,base+' personal picker contains only owner and unassigned');
  await ben.page.addScriptTag({path:require.resolve('../frontend/node_modules/axe-core/axe.min.js')});
  const pickerViolations=await ben.page.evaluate(async()=> (await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id));
  check(pickerViolations.length===0,base+' mobile assignment picker axe '+pickerViolations.join(','));
  check(await ben.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),base+' mobile assignment picker no overflow');

  for(const person of [ben,asha,chen,dana,admin])await person.ctx.close();
 }
 console.log(`${count} assignment browser checks passed`);
}finally{await browser.close();}
