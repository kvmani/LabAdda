// C3 conversion: disposable proxy fixtures only. Revokes Ben's source grant last.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{chromium}=require('playwright');
const origin='http://127.0.0.1:8080';
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let count=0;
function check(value,label){assert.ok(value,label);count++;console.log('PASS '+label);}
async function login(base,name){
 const ctx=await browser.newContext({viewport:{width:1400,height:1100}}),page=await ctx.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+base+'/');await page.getByLabel('Username').fill(name);await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('button',{name:'Sign out'}).waitFor();
 const session=await(await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
 return {ctx,page,errors,session,api:origin+base+'/api/v1',headers:{'X-CSRF-Token':session.csrf_token}};
}
async function call(user,path,data,method=data?'POST':'GET'){
 const r=await user.ctx.request.fetch(user.api+path,{method,headers:user.headers,data});assert.ok(r.ok(),await r.text());return r.json();
}
async function accessible(user,base,label){
 for(const width of [1400,390]){
  await user.page.setViewportSize({width,height:1100});await user.page.addScriptTag({path:require.resolve('../frontend/node_modules/axe-core/axe.min.js')});
  const violations=await user.page.evaluate(async()=>(await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations.map(v=>v.id));
  check(violations.length===0,base+' '+label+' accessibility '+width+' '+violations.join(','));
  check(await user.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),base+' '+label+' no overflow '+width);
 }
 await user.page.setViewportSize({width:1400,height:1100});
}
async function list(user,workspace,title){return call(user,'/todos/lists',{client_id:crypto.randomUUID(),title,workspace_id:workspace});}
async function postForm(user,base,workspace,body){
 await user.page.goto(origin+base+`/w/${workspace}/noticeboard`);const card=user.page.getByRole('article').filter({has:user.page.getByText(body,{exact:true})});await card.getByRole('button',{name:'Create task',exact:true}).click();return user.page.getByRole('form',{name:'Create task from conversation',exact:true});
}
async function tasks(user,base,workspace,row){await user.page.goto(origin+base+(workspace?`/w/${workspace}/todos`:'/todos'));await user.page.getByRole('button',{name:row.title,exact:true}).click();}
try{
 for(const base of ['', '/labadda-staging']){
  const ben=await login(base,'ben'),chen=await login(base,'chen'),admin=await login(base,'admin');
  const spaces=(await call(ben,'/workspaces')).workspaces,section=spaces.find(w=>w.name==='Thin Films Section'),division=spaces.find(w=>w.name==='Surface Science Division');
  const privateList=await list(ben,null,'Personal followups'),sharedList=await list(ben,section.id,'Section actions'),divisionList=await list(ben,division.id,'Division actions');
  const original='Review vacancy controls α\n<script>window.fixtureExecuted=true</script> is inert research text.';
  const post=await call(ben,`/workspaces/${section.id}/posts`,{body:original,client_id:crypto.randomUUID()});
  let form=await postForm(ben,base,section.id,original);
  check(await form.getByLabel('Task description',{exact:true}).inputValue()===original,base+' post text starts an editable reviewed copy');
  await form.getByLabel('Task destination',{exact:true}).selectOption('personal');await form.getByLabel('Destination list',{exact:true}).selectOption(privateList.id);
  await accessible(ben,base,'conversion form');
  await form.getByLabel('Task title',{exact:true}).fill('Private control check');await form.getByLabel('Task description',{exact:true}).fill('Only my reviewed followup.');
  await ben.page.route('**/api/v1/todos/lists/*/from-conversation',async route=>{await route.fetch();await route.abort();},{times:1});
  await form.getByRole('button',{name:'Save conversation task',exact:true}).click();await form.getByRole('button',{name:'Retry same task copy',exact:true}).waitFor();
  check(await form.getByLabel('Task destination',{exact:true}).isDisabled()&&await form.getByLabel('Task title',{exact:true}).isDisabled(),base+' lost reply freezes original text and audience');
  await form.getByRole('button',{name:'Retry same task copy',exact:true}).click();await ben.page.getByText('Task saved. Its source link still requires access to the original conversation.',{exact:true}).waitFor();
  const personal=(await call(ben,`/todos/lists/${privateList.id}/tasks`)).items;
  check(personal.length===1&&personal[0].description==='Only my reviewed followup.'&&personal[0].has_source,base+' retry creates exactly one reviewed task and reference');
  await tasks(ben,base,null,privateList);await ben.page.getByRole('button',{name:'View source conversation',exact:true}).click();await ben.page.getByRole('region',{name:'Task source conversation'}).getByText(original,{exact:true}).waitFor();
  await accessible(ben,base,'protected source view');
  check(await ben.page.locator('script').filter({hasText:'window.fixtureExecuted'}).count()===0,base+' source text is rendered without HTML execution');
  check((await chen.ctx.request.get(chen.api+`/todos/lists/${privateList.id}/tasks/${personal[0].id}/source`)).status()===404,base+' personal reference is owner-only');
  // Same-source shared task needs no broader-audience checkbox.
  form=await postForm(ben,base,section.id,original);await form.getByLabel('Destination list',{exact:true}).selectOption(sharedList.id);await form.getByLabel('Task title',{exact:true}).fill('Section control check');
  check(await form.getByRole('checkbox').count()===0,base+' same workspace audience is shown without a broader-copy confirmation');
  await form.getByRole('button',{name:'Save conversation task',exact:true}).click();await ben.page.getByText('Task saved. Its source link still requires access to the original conversation.',{exact:true}).waitFor();
  // Chat-to-division requires an explicit audience choice and confirmation.
  const chatText='Repeat three GC controls before the division review.';
  await call(ben,`/workspaces/${section.id}/chat`,{body:chatText,client_id:crypto.randomUUID()});
  await ben.page.goto(origin+base+`/w/${section.id}/chat`);await ben.page.getByRole('listitem').filter({has:ben.page.getByText(chatText,{exact:true})}).getByRole('button',{name:'Create task',exact:true}).click();
  form=ben.page.getByRole('form',{name:'Create task from conversation',exact:true});await form.getByLabel('Task destination',{exact:true}).selectOption(division.id);await form.getByLabel('Destination list',{exact:true}).selectOption(divisionList.id);
  check(await form.getByRole('button',{name:'Save conversation task',exact:true}).isDisabled(),base+' different audience cannot save without confirmation');
  await form.getByRole('checkbox').check();await form.getByLabel('Task destination',{exact:true}).selectOption('personal');await form.getByLabel('Task destination',{exact:true}).selectOption(division.id);await form.getByLabel('Destination list',{exact:true}).selectOption(divisionList.id);
  check(!await form.getByRole('checkbox').isChecked(),base+' changing destination resets audience confirmation');
  await form.getByRole('checkbox').check();await form.getByLabel('Task title',{exact:true}).fill('Reviewed division control action');await form.getByLabel('Task description',{exact:true}).fill('Reviewed controls for the common division.');await form.getByRole('button',{name:'Save conversation task',exact:true}).click();await ben.page.getByText('Task saved. Its source link still requires access to the original conversation.',{exact:true}).waitFor();
  const converted=(await call(ben,`/todos/lists/${divisionList.id}/tasks`)).items[0],sourcePath=`/todos/lists/${divisionList.id}/tasks/${converted.id}/source`;
  await tasks(chen,base,division.id,divisionList);await chen.page.getByRole('button',{name:'View source conversation',exact:true}).click();await chen.page.getByText('Source unavailable or no longer accessible.',{exact:true}).waitFor();
  check(await chen.page.getByText('Reviewed controls for the common division.',{exact:true}).isVisible()&&await chen.page.getByText(chatText,{exact:true}).count()===0,base+' sibling sees reviewed division task without protected source body');
  check((await chen.ctx.request.get(chen.api+sourcePath)).status()===404,base+' direct source lookup does not grant sibling access');
  // Real pagination must not submit a previous page's hidden selected list.
  for(let i=0;i<25;i++)await list(ben,null,'Private paged '+i);
  form=await postForm(ben,base,section.id,original);await form.getByLabel('Task destination',{exact:true}).selectOption('personal');await form.getByLabel('Destination list',{exact:true}).selectOption({index:1});await form.getByRole('button',{name:'More destination lists',exact:true}).click();
  check(await form.getByLabel('Destination list',{exact:true}).inputValue()===''&&await form.getByRole('button',{name:'Save conversation task',exact:true}).isDisabled(),base+' list paging clears hidden destination choice');
  // Hold a successful first source lookup, revoke only source access, then release.
  await tasks(ben,base,division.id,divisionList);
  let release,captured;const held=new Promise(resolve=>release=resolve),ready=new Promise(resolve=>captured=resolve);
  await ben.page.route('**/api/v1'+sourcePath,async route=>{const response=await route.fetch();captured();await held;await route.fulfill({response});},{times:1});
  const delivered=ben.page.waitForResponse(r=>r.url().endsWith(sourcePath));
  await ben.page.getByRole('button',{name:'View source conversation',exact:true}).click();await ready;
  // Retain division read authority while removing the child-section source grant.
  await call(admin,`/admin/workspaces/${division.id}/memberships`,{user_id:ben.session.user.id,role:'member'},'PUT');
  const removal=await admin.ctx.request.delete(admin.api+`/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,{headers:admin.headers});assert.equal(removal.status(),200);
  await ben.page.getByText('Source unavailable or no longer accessible.',{exact:true}).waitFor();
  await ben.page.evaluate(text=>{window.__sourceLeaked=false;new MutationObserver(()=>{if(document.body.innerText.includes(text))window.__sourceLeaked=true;}).observe(document.body,{childList:true,subtree:true,characterData:true});},chatText);
  release();await(await delivered).finished();await ben.page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await ben.page.getByRole('button',{name:'View source conversation',exact:true}).waitFor();
  check(!await ben.page.evaluate(()=>window.__sourceLeaked)&&await ben.page.getByText(chatText,{exact:true}).count()===0,base+' delayed source response cannot restore text after source-only revocation');
  check((await call(ben,`/todos/lists/${divisionList.id}/tasks`)).items.length===1,base+' reviewed destination task survives source revocation');
  check(ben.errors.length===0&&chen.errors.length===0,base+' no browser exceptions');
  await Promise.all([ben.ctx.close(),chen.ctx.close(),admin.ctx.close()]);
 }
 console.log(`${count} conversion browser checks passed`);
}catch(error){for(const [i,ctx] of browser.contexts().entries())for(const page of ctx.pages()){await page.screenshot({path:`/tmp/c3-failure-${i}.png`,fullPage:true});console.error((await page.locator('main').innerText()).slice(-5000));}throw error;}finally{await browser.close();}
