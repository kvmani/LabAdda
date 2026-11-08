// Complements governance.mjs after operator CLI inspection of that disposable stack.
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {mkdirSync} from 'node:fs';
const {chromium}=createRequire(import.meta.url)('playwright');
const out=process.argv[2] ?? '/tmp/labadda-governance'; mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
try {
  for(const base of ['', '/labadda-staging']) {
    const ctx=await browser.newContext({viewport:{width:1400,height:1100},timezoneId:'Asia/Kolkata'});
    const page=await ctx.newPage(); await page.goto('http://127.0.0.1:8080'+base+'/admin');
    await page.getByLabel('Username').fill('admin');
    await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('heading',{name:'Referenced file inspections'}).waitFor();
    const data=await (await ctx.request.get('http://127.0.0.1:8080'+base+'/api/v1/admin/storage-inspections')).json();
    const checked=data.inspections[0].summary.checked_assets;
    assert.ok(checked > 0);
    assert.equal(data.inspections[0].summary.issue_count,0);
    await page.getByText(new RegExp(`completed · ${checked} asset rows checked · 0 issues`)).first().waitFor();
    assert.equal(data.inspections[0].summary.preview_integrity,'unverified');
    assert.equal(data.inspections[0].summary.complete_for_enforcement,false);
    await page.screenshot({path:out+(base?'/admin-prefix.png':'/admin-root.png'),fullPage:true});
    console.log('PASS '+base+': original inspection receipt shown without enforcement authority');
    await ctx.close();
  }
} finally {await browser.close();}
