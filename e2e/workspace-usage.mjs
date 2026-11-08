// Fresh local synthetic proxy stack: workspace ownership and current-access UI.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const require=createRequire(import.meta.url), {chromium}=require('playwright');
const axe=require.resolve('../frontend/node_modules/axe-core/axe.min.js');
const origin='http://127.0.0.1:8080',out=process.argv[2] ?? '/tmp/labadda-workspace-usage';
mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let passed=0;
function check(value,label){assert.ok(value,label);passed++;console.log('PASS '+label);}
async function login(base,name){
  const ctx=await browser.newContext({viewport:{width:1400,height:1100}}),page=await ctx.newPage();
  await page.goto(origin+base+'/');
  await page.getByLabel('Username').fill(name);
  await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'Sign out'}).waitFor();
  const session=await (await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
  return {ctx,page,session};
}
async function audit(page){
  await page.addScriptTag({path:axe});
  return page.evaluate(async()=>{
    const result=await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});
    return result.violations.map(v=>({id:v.id,impact:v.impact}));
  });
}
try{
  for(const base of ['', '/labadda-staging']){
    const ben=await login(base,'ben'),asha=await login(base,'asha'),chen=await login(base,'chen'),admin=await login(base,'admin');
    const api=origin+base+'/api/v1';
    const spaces=await (await ben.ctx.request.get(api+'/workspaces')).json();
    const section=spaces.workspaces.find(w=>w.name==='Thin Films Section');
    const division=spaces.workspaces.find(w=>w.name==='Surface Science Division');
    const pdf=Buffer.from('%PDF-1.4\nWorkspace colleague handoff\n%%EOF');
    const upload=await asha.ctx.request.post(api+'/uploads',{headers:{'X-CSRF-Token':asha.session.csrf_token},
      multipart:{file:{name:'private-colleague-file.pdf',mimeType:'application/pdf',buffer:pdf}}});
    assert.equal(upload.status(),201);
    const asset=await upload.json();
    const post=await asha.ctx.request.post(api+'/workspaces/'+section.id+'/posts',{
      headers:{'X-CSRF-Token':asha.session.csrf_token},data:{body:'Colleague shared fixture',attachment_ids:[asset.id]}});
    assert.equal(post.status(),201);
    const note=await ben.ctx.request.post(api+'/notes',{headers:{'X-CSRF-Token':ben.session.csrf_token},data:{title:'private-note-marker',body:'private-body-marker'}});
    assert.equal(note.status(),201);
    await ben.page.goto(origin+base+'/w/'+section.id+'/noticeboard');
    await ben.page.getByRole('link',{name:'Storage',exact:true}).click();
    await ben.page.getByRole('heading',{name:'Workspace storage usage'}).waitFor();
    await ben.page.getByText('Original files retained',{exact:true}).waitFor();
    const measured=await (await ben.ctx.request.get(api+'/workspaces/'+section.id+'/usage')).json();
    check(measured.files.retained_original_bytes===pdf.length && measured.files.retained_files===1,base+': shared file counts include colleague contributions');
    check(!('note' in measured.logical_charges.by_type),base+': private notes excluded from workspace buckets');
    check(!('database' in measured) && !('filesystem' in measured),base+': shared physical overhead excluded');
    const text=await ben.page.locator('body').innerText();
    check(!text.includes('private-colleague-file') && !text.includes('private-note-marker') && !text.includes('private-body-marker'),base+': view does not disclose filenames or private content');
    check(measured.files.pending_upload_bytes===null && measured.workspace_budget.bytes===null && !measured.complete_for_enforcement,base+': unknown attribution and budget remain explicit');
    const desktopAudit=await audit(ben.page);
    check(desktopAudit.length===0,base+': desktop workspace usage has no axe findings '+JSON.stringify(desktopAudit));
    await ben.page.screenshot({path:out+(base?'/workspace-prefix.png':'/workspace-root.png'),fullPage:true});
    await ben.page.setViewportSize({width:390,height:844});
    check(await ben.page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),base+': storage tab and counters fit a phone');
    const mobileAudit=await audit(ben.page);
    check(mobileAudit.length===0,base+': mobile workspace usage has no axe findings '+JSON.stringify(mobileAudit));
    await ben.page.screenshot({path:out+(base?'/workspace-prefix-mobile.png':'/workspace-root-mobile.png'),fullPage:true});
    await ben.page.goto(origin+base+'/w/'+division.id+'/usage');
    await ben.page.getByText('Original files retained',{exact:true}).waitFor();
    const parent=await (await ben.ctx.request.get(api+'/workspaces/'+division.id+'/usage')).json();
    check(parent.files.retained_files===0 && parent.logical_charges.live_logical_bytes===0,base+': parent totals exclude child workspaces');
    check((await chen.ctx.request.get(api+'/workspaces/'+section.id+'/usage')).status()===404 &&
          (await admin.ctx.request.get(api+'/workspaces/'+section.id+'/usage')).status()===404,base+': sibling and administrator without grants denied');
    await ben.page.goto(origin+base+'/w/'+section.id+'/usage');
    await ben.page.getByText('Original files retained',{exact:true}).waitFor();
    const users=await (await admin.ctx.request.get(api+'/admin/users')).json();
    const benId=users.users.find(u=>u.username==='ben').id;
    const revoke=await admin.ctx.request.delete(api+'/admin/workspaces/'+section.id+'/memberships/'+benId,
      {headers:{'X-CSRF-Token':admin.session.csrf_token}});
    assert.equal(revoke.status(),200);
    await ben.page.evaluate(()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Refresh workspace usage')?.click());
    await ben.page.waitForFunction(()=>!document.body.innerText.includes('Original files retained'));
    check((await ben.ctx.request.get(api+'/workspaces/'+section.id+'/usage')).status()===404,base+': revoked refresh clears counters and is denied');
    for(const actor of [ben,asha,chen,admin]) await actor.ctx.close();
  }
  console.log(`${passed} workspace usage browser checks passed`);
}finally{await browser.close();}
