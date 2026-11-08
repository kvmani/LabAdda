// Real browser metadata views after new image creation. Local synthetic stack only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const {chromium}=createRequire(import.meta.url)('playwright');
const origin='http://127.0.0.1:8080';
const output=process.argv[2] ?? '/tmp/labadda-preview-observations';
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let passed=0;
function check(value,label){assert.ok(value,label);passed++;console.log('PASS '+label);}
async function login(base,user){
  const ctx=await browser.newContext({viewport:{width:1400,height:1100}}),page=await ctx.newPage();
  await page.goto(origin+base+'/');
  await page.getByLabel('Username').fill(user);
  await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'Sign out'}).waitFor();
  const session=await (await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
  return {ctx,page,session};
}
try{
  for(const base of ['', '/labadda-staging']){
    const ben=await login(base,'ben'),admin=await login(base,'admin'),api=origin+base+'/api/v1';
    const before=await (await ben.ctx.request.get(api+'/usage')).json();
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAHUlEQVR4nGP4z8BAEhrVMKphVMOohlENIxoGAAD4/H8BWrLzvAAAAABJRU5ErkJggg==','base64');
    const response=await ben.ctx.request.post(api+'/uploads',{headers:{'X-CSRF-Token':ben.session.csrf_token},
      multipart:{file:{name:'private-derivative-fixture.png',mimeType:'image/png',buffer:png}}});
    assert.equal(response.status(),201);
    const asset=await response.json();
    const preview=await (await ben.ctx.request.get(origin+asset.preview_url)).body();
    const after=await (await ben.ctx.request.get(api+'/usage')).json();
    check(after.measurement.tracked_preview_bytes===before.measurement.tracked_preview_bytes+preview.length,base+': recorded preview bytes match stored raster');
    check(after.measurement.unknown_preview_files===before.measurement.unknown_preview_files,base+': new preview does not conceal unknown history');
    check(after.runtime_limit.bytes===before.runtime_limit.bytes && after.measurement.complete_for_enforcement===false,base+': pilot allowance remains unchanged and measurement partial');
    await ben.page.goto(origin+base+'/usage');
    await ben.page.getByText('Previews with recorded measurements',{exact:true}).waitFor();
    check(await ben.page.getByText('Previews with unknown measurements',{exact:true}).isVisible(),base+': user sees measured and unknown categories');
    await ben.page.screenshot({path:output+(base?'/user-prefix.png':'/user-root.png'),fullPage:true});
    await admin.page.goto(origin+base+'/admin');
    await admin.page.getByText('Previews with recorded measurements',{exact:true}).waitFor();
    check(!(await admin.page.locator('body').innerText()).includes('private-derivative-fixture'),base+': admin observation does not expose private filename');
    await admin.page.screenshot({path:output+(base?'/admin-prefix.png':'/admin-root.png'),fullPage:true});
    await ben.ctx.close();await admin.ctx.close();
  }
  console.log(`${passed} preview observation browser checks passed`);
}finally{await browser.close();}
