// Actual browser checks for observation-only P5 foundations at root and a prefix.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const {chromium} = createRequire(import.meta.url)('playwright');
const origin = process.argv[2] ?? 'http://127.0.0.1:8080';
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw Error('Use a local disposable test stack');
const out = process.argv[3] ?? '/tmp/labadda-governance';
mkdirSync(out,{recursive:true});
const browser = await chromium.launch({executablePath: process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let checks = 0;
function check(value, text) { assert.ok(value,text); checks++; console.log('PASS '+text); }
async function signIn(base,name) {
  const ctx = await browser.newContext({viewport:{width:1400,height:1100},timezoneId:'Asia/Kolkata'});
  const page = await ctx.newPage();
  await page.goto(origin+base+'/');
  await page.getByLabel('Username').fill(name);
  await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('button',{name:'Sign out'}).waitFor();
  return {ctx,page};
}
try {
  for(const base of ['', '/labadda-staging']) {
    const {ctx,page} = await signIn(base,'admin');
    await page.goto(origin+base+'/admin');
    await page.getByRole('heading',{name:'Site proposal revision 0'}).waitFor();
    await page.getByLabel('Proposed user limit (MiB)').fill('750');
    await page.getByLabel('Proposal reason').fill('Synthetic browser capacity review');
    await page.getByRole('button',{name:'Save non-enforcing proposal'}).click();
    await page.getByText('Proposal saved. No limits or retention rules were activated.',{exact:true}).waitFor();
    await page.getByRole('heading',{name:'Site proposal revision 1'}).waitFor();
    check(await page.getByText('Draft only',{exact:true}).isVisible(),base+': proposal saved without activation');
    const session = await (await ctx.request.get(origin+base+'/api/v1/auth/session')).json();
    const before = await (await ctx.request.get(origin+base+'/api/v1/usage')).json();
    check(before.runtime_limit.bytes === 500*1024**2,base+': pilot limit remains 500 MiB');
    await page.getByLabel('Proposed user limit (MiB)').fill('1');
    await page.getByRole('button',{name:'Save non-enforcing proposal'}).click();
    await page.getByRole('alert').filter({hasText:'File limit must fit'}).waitFor();
    check(await page.getByLabel('Proposed user limit (MiB)').inputValue() === '1',base+': rejected form preserves input');
    await page.getByLabel('Proposed user limit (MiB)').fill('750');
    const extra = await ctx.request.post(origin+base+'/api/v1/admin/policy-drafts',{
      headers:{'X-CSRF-Token':session.csrf_token},data:{base_revision:1,reason:'Concurrent synthetic edit',profile:{}}});
    assert.equal(extra.status(),201);
    await page.getByRole('button',{name:'Save non-enforcing proposal'}).click();
    await page.getByRole('alert').filter({hasText:'newer proposal exists'}).waitFor();
    check(await page.getByLabel('Proposal reason').inputValue()==='Synthetic browser capacity review',base+': conflict preserves reason');
    await page.getByRole('button',{name:'Reload observations',exact:true}).click();
    await page.getByRole('heading',{name:'Site proposal revision 2'}).waitFor();
    await page.getByRole('button',{name:'Record partial observation'}).click();
    await page.getByText('Partial observation recorded.',{exact:true}).waitFor();
    await page.screenshot({path:out+(base?'/admin-prefix.png':'/admin-root.png'),fullPage:true});
    check(true,base+': admin observation and history rendered');
    const ben = await signIn(base,'ben');
    const bs = await (await ben.ctx.request.get(origin+base+'/api/v1/auth/session')).json();
    const upload = await ben.ctx.request.post(origin+base+'/api/v1/uploads',{
      headers:{'X-CSRF-Token':bs.csrf_token},multipart:{file:{name:'private-filename.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nfixture\n%%EOF')}}});
    assert.equal(upload.status(),201);
    await ben.page.getByRole('link',{name:'My storage usage',exact:true}).click();
    await ben.page.getByRole('heading',{name:'Pilot upload counter'}).waitFor();
    check(await ben.page.getByText(/1 files/).isVisible(),base+': user sees own original counter');
    check(!(await ben.page.locator('body').innerText()).includes('private-filename'),base+': usage does not expose filenames');
    const denied = await ben.ctx.request.get(origin+base+'/api/v1/admin/usage');
    check(denied.status()===403,base+': member denied site measurements');
    await ben.page.setViewportSize({width:390,height:844});
    await ben.page.getByLabel('Switch workspace').selectOption('usage');
    await ben.page.getByRole('heading',{name:'Pilot upload counter'}).waitFor();
    check(true,base+': mobile switcher opens storage usage');
    await ben.page.setViewportSize({width:1400,height:1100});
    await ben.page.screenshot({path:out+(base?'/user-prefix.png':'/user-root.png'),fullPage:true});
    await ben.ctx.close(); await ctx.close();
  }
  console.log(`${checks} governance browser checks passed`);
} finally {await browser.close();}
