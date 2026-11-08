// Fresh local synthetic stack. Actual file-picker recovery at root and prefix.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync} from 'node:fs';
const {chromium} = createRequire(import.meta.url)('playwright');
const origin = process.argv[2] ?? 'http://127.0.0.1:8080';
if (!['localhost','127.0.0.1'].includes(new URL(origin).hostname)) throw Error('Use a disposable local stack');
const output = process.argv[3] ?? '/tmp/labadda-upload-recovery';
mkdirSync(output,{recursive:true});
const browser = await chromium.launch({executablePath:process.env.LABADDA_CHROMIUM ?? '/usr/bin/chromium'});
let checks = 0;
function check(value,label) { assert.ok(value,label); checks++; console.log('PASS '+label); }
try {
  for (const base of ['', '/labadda-staging']) {
    const ctx = await browser.newContext({viewport:{width:1280,height:960}}), page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin+base+'/');
    await page.getByLabel('Username').fill('ben');
    await page.getByLabel('Password').fill(process.env.LABADDA_FIXTURE_PASSWORD ?? 'fixture-pass-123');
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.getByRole('button',{name:'Sign out'}).waitFor();
    const api = origin+base+'/api/v1';
    const spaces = await (await ctx.request.get(api+'/workspaces')).json();
    const section = spaces.workspaces.find(w=>w.name==='Thin Films Section');
    const initial = await (await ctx.request.get(api+'/usage')).json();
    await page.goto(origin+base+'/w/'+section.id+'/noticeboard');
    await page.getByLabel('Message',{exact:true}).fill('Synthetic recovered colleague attachment');
    const posted = [];
    let lose = true;
    let truncate = false;
    await page.route(api+'/uploads', async route => {
      posted.push(route.request().headers()['idempotency-key']);
      const response = await route.fetch();
      assert.equal(response.status(),201);
      if (lose) { lose=false; await route.abort('failed'); }
      else if (truncate) { truncate=false; await route.fulfill({status:201,contentType:'application/json',body:'{'}); }
      else await route.fulfill({response});
    });
    const pdf = {name:'recovered.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nUI recovery fixture\n%%EOF')};
    await page.getByLabel('Attach',{exact:true}).setInputFiles(pdf);
    await page.getByRole('button',{name:'Check upload result',exact:true}).waitFor();
    check(await page.getByRole('button',{name:'Post',exact:true}).isDisabled(),base+': unresolved upload prevents incomplete post');
    check(await page.getByLabel('Message',{exact:true}).inputValue()==='Synthetic recovered colleague attachment',base+': text draft preserved');
    check(/^[A-Za-z0-9_-]{8,64}$/.test(posted[0]),base+': file picker sends valid request key');
    await page.screenshot({path:output+(base?'/notice-prefix.png':'/notice-root.png'),fullPage:true});
    await page.getByRole('button',{name:'Check upload result',exact:true}).click();
    await page.getByRole('button',{name:'Remove recovered.pdf'}).waitFor();
    check(posted.length===1,base+': result check recovers file without another upload');
    lose=true;
    await page.getByLabel('Attach',{exact:true}).setInputFiles({...pdf,name:'retry.pdf'});
    await page.getByRole('button',{name:'Retry same file',exact:true}).click();
    await page.getByRole('button',{name:'Remove retry.pdf'}).waitFor();
    check(posted.length===3 && posted[1]===posted[2] && posted[0]!==posted[1],base+': explicit retry reuses its key');
    truncate=true;
    await page.getByLabel('Attach',{exact:true}).setInputFiles({...pdf,name:'truncated.pdf'});
    await page.getByRole('button',{name:'Retry same file',exact:true}).click();
    await page.getByRole('button',{name:'Remove truncated.pdf'}).waitFor();
    check(posted.length===5 && posted[3]===posted[4],base+': truncated successful response retains same-key retry');
    const measured = await (await ctx.request.get(api+'/usage')).json();
    check(measured.measurement.tracked_files===initial.measurement.tracked_files+3,base+': three selected files produce three assets across lost replies');
    await page.getByRole('button',{name:'Post',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Posted'}).waitFor();
    await page.reload();
    const post = page.locator('.post').filter({hasText:'Synthetic recovered colleague attachment'});
    await post.waitFor();
    check(await post.locator('.attachments li').count()===3,base+': recovered files post durably once');

    await page.goto(origin+base+'/w/'+section.id+'/board');
    await page.getByRole('status').filter({hasText:'Saved'}).waitFor();
    lose=true;
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAHUlEQVR4nGP4z8BAEhrVMKphVMOohlENIxoGAAD4/H8BWrLzvAAAAABJRU5ErkJggg==','base64');
    await page.getByLabel('Image to place on the board').setInputFiles({name:'recovered-diagram.png',mimeType:'image/png',buffer:png});
    await page.getByRole('button',{name:'Check upload result',exact:true}).waitFor();
    check(await page.getByRole('button',{name:'🖼 Image',exact:true}).isDisabled(),base+': board blocks another image while unresolved');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:output+(base?'/board-prefix-mobile.png':'/board-root-mobile.png'),fullPage:true});
    await page.getByRole('button',{name:'Check upload result',exact:true}).click();
    await page.waitForFunction(()=>/rev 1\b/.test(document.querySelector('.toolbar')?.textContent ?? ''));
    const board = await (await ctx.request.get(api+'/workspaces/'+section.id+'/board')).json();
    check(board.ops.filter(op=>op.type==='add' && op.payload.kind==='image').length===1,base+': recovered image placed once');
    check(posted.length===6,base+': board recovery reads receipt without upload duplication');
    check(errors.length===0,base+': no uncaught browser errors');
    await ctx.close();
  }
  console.log(`${checks} upload recovery UI checks passed`);
} finally { await browser.close(); }
