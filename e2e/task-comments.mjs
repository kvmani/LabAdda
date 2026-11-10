// C2 comments: run on fresh disposable proxy fixtures. Membership is revoked at the end.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url),{chromium}=require('playwright');
const origin='http://127.0.0.1:8080',out=process.argv[2] ?? '/tmp/labadda-task-comments';mkdirSync(out,{recursive:true});
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
 const list=await(await user.ctx.request.post(user.api+'/todos/lists',{headers:user.headers,data:{client_id:crypto.randomUUID(),title,workspace_id:workspace}})).json();
 const task=await(await user.ctx.request.post(user.api+`/todos/lists/${list.id}/tasks`,{headers:user.headers,data:{client_id:crypto.randomUUID(),title:title+' task'}})).json();
 return {list,task,path:`/todos/lists/${list.id}/tasks/${task.id}/comments`};
}
async function open(user,base,workspace,record){
 await user.page.goto(origin+base+(workspace?`/w/${workspace}/todos`:'/todos'));
 await user.page.getByRole('button',{name:record.list.title,exact:true}).click();
 await user.page.getByRole('button',{name:'View comments',exact:true}).click();
 const region=user.page.getByRole('region',{name:'Task comments',exact:true});
 await region.getByRole('button',{name:'Refresh comments',exact:true}).waitFor();return region;
}
async function post(region,text){
 await region.getByLabel('New task comment',{exact:true}).fill(text);await region.getByRole('button',{name:'Post comment',exact:true}).click();
 await region.getByRole('listitem').getByText(text,{exact:true}).waitFor();
}
try{
 for(const base of ['', '/labadda-staging']){
  const ben=await login(base,'ben'),asha=await login(base,'asha'),chen=await login(base,'chen'),dana=await login(base,'dana'),admin=await login(base,'admin');
  const spaces=(await(await ben.ctx.request.get(ben.api+'/workspaces')).json()).workspaces;
  const section=spaces.find(w=>w.name==='Thin Films Section'),division=spaces.find(w=>w.name==='Surface Science Division');
  const shared=await create(ben,section.id,'Research discussion'),personal=await create(ben,null,'Private followup'),other=await create(ben,null,'Other private research'),div=await create(ben,division.id,'Division analysis');
  let region=await open(ben,base,section.id,shared);await region.getByText('No comments yet.',{exact:true}).waitFor();
  const text='Calibrate α first.\n<script>alert("inert fixture")</script> is plain text.';
  await region.getByLabel('New task comment',{exact:true}).fill(text);
  await ben.page.route('**/api/v1/todos/lists/*/tasks/*/comments',async route=>{await route.fetch();await route.abort();},{times:1});
  await region.getByRole('button',{name:'Post comment',exact:true}).click();await region.getByRole('button',{name:'Retry same comment',exact:true}).waitFor();
  check(await region.getByLabel('New task comment',{exact:true}).isDisabled(),base+' unknown comment freezes original intent');
  await region.getByRole('button',{name:'Retry same comment',exact:true}).click();await region.getByRole('listitem').getByText(text,{exact:true}).waitFor();
  const committed=(await(await ben.ctx.request.get(ben.api+shared.path)).json()).items;
  check(committed.length===1 && committed[0].sequence===1,base+' lost reply recovers exactly one comment');
  check(await region.locator('script').count()===0,base+' active-looking text is escaped');
  check((await(await ben.ctx.request.get(ben.api+shared.path.replace('/comments',''))).json()).revision===1,base+' comment does not change task revision');
  const ashaRegion=await open(asha,base,section.id,shared);await ashaRegion.getByText(text,{exact:true}).waitFor();
  await post(ashaRegion,'Instrument calibrated before this run.');
  await region.getByRole('button',{name:'Refresh comments',exact:true}).click();await region.getByText('Instrument calibrated before this run.',{exact:true}).waitFor();
  check(await region.getByText('Asha Rao',{exact:true}).count()===1,base+' colleague authorship and discussion visible after refresh');
  const draft='Unsent research followup β';await region.getByLabel('New task comment',{exact:true}).fill(draft);
  const refreshed=ben.page.waitForResponse(r=>r.request().method()==='GET' && r.url().endsWith(`/todos/lists/${shared.list.id}/tasks`));
  await ben.page.getByRole('button',{name:'Refresh tasks',exact:true}).click();await refreshed;await ben.page.waitForTimeout(100);
  check(await region.getByLabel('New task comment',{exact:true}).inputValue()===draft,base+' draft survives same-list refresh');
  await ben.page.getByRole('button',{name:'Edit task: '+shared.task.title,exact:true}).click();await ben.page.getByLabel('Priority',{exact:true}).selectOption('high');
  await ben.page.getByRole('button',{name:'Save task',exact:true}).click();await ben.page.getByText('To do · high priority',{exact:true}).waitFor();
  check(await region.getByLabel('New task comment',{exact:true}).inputValue()===draft,base+' draft survives task field edit');
  await region.getByRole('button',{name:'Post comment',exact:true}).click();await region.getByText(draft,{exact:true}).waitFor();
  for(const outsider of [chen,dana,admin])check((await outsider.ctx.request.get(outsider.api+shared.path)).status()===404,base+' sibling/parent/admin cannot read section discussion');
  const divisionRegion=await open(chen,base,division.id,div);await post(divisionRegion,'Cross-section correlation is ready for division review.');
  check((await(await dana.ctx.request.get(dana.api+div.path)).json()).items[0].author.id===chen.session.user.id,base+' division discussion spans sibling sections and steward');
  const privateRegion=await open(ben,base,null,personal);await post(privateRegion,'Owner-only experimental note.');
  for(const outsider of [asha,chen,dana,admin])check((await outsider.ctx.request.get(outsider.api+personal.path)).status()===404,base+' personal discussion denies all colleagues/admin');
  let release,entered;const gate=new Promise(resolve=>{release=resolve;}),started=new Promise(resolve=>{entered=resolve;});
  await ben.page.route('**/api/v1'+personal.path,async route=>{const response=await route.fetch();entered();await gate;await route.fulfill({response});},{times:1});
  await privateRegion.getByRole('button',{name:'Refresh comments',exact:true}).click();await started;
  await ben.page.getByRole('button',{name:other.list.title,exact:true}).click();await ben.page.getByRole('heading',{name:other.task.title,exact:true}).waitFor();
  const finished=ben.page.waitForResponse(r=>r.url().endsWith(personal.path));release();await finished;await ben.page.waitForTimeout(100);
  check(await ben.page.getByText('Owner-only experimental note.',{exact:true}).count()===0 && await ben.page.getByRole('region',{name:'Task comments',exact:true}).count()===0,base+' delayed comments cannot populate another task');
  const readOnly=await asha.ctx.request.patch(asha.api+'/workspaces/'+section.id+'/policy',{headers:asha.headers,data:{posting_policy:'read_only'}});
  check(readOnly.status()===200,base+' real workspace read-only policy applied');
  region=await open(ben,base,section.id,shared);await region.getByText(draft,{exact:true}).waitFor();
  check(await region.getByRole('button',{name:'Post comment',exact:true}).count()===0,base+' read-only view hides posting controls');
  check((await ben.ctx.request.post(ben.api+shared.path,{headers:ben.headers,data:{client_id:crypto.randomUUID(),body:'Denied'}})).status()===403,base+' read-only direct posting denied');
  for(const width of [1400,390]){
   await ben.page.setViewportSize({width,height:1100});await ben.page.addScriptTag({path:require.resolve('../frontend/node_modules/axe-core/axe.min.js')});
   const violations=await ben.page.evaluate(async()=> (await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id));
   check(violations.length===0,base+' comments axe '+width+' '+violations.join(','));check(await ben.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),base+' comments overflow '+width);
   await ben.page.screenshot({path:out+'/'+(base?'prefix':'root')+'-'+width+'.png',fullPage:true});
  }
  await admin.ctx.request.delete(admin.api+`/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,{headers:admin.headers});
  check((await ben.ctx.request.get(ben.api+shared.path)).status()===404,base+' revoked discussion access denied');
  for(const person of [ben,asha,chen,dana,admin])await person.ctx.close();
 }
 console.log(`${count} comment browser checks passed`);
}finally{await browser.close();}
