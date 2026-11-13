// Browser flows through the real proxy for a root and a prefixed instance.
// Usage: node e2e/flows.mjs [origin] [base...]   e.g. node e2e/flows.mjs http://127.0.0.1:8080 "" /labadda-staging
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = process.argv[2] ?? "http://127.0.0.1:8080";
const bases = process.argv.length > 3 ? process.argv.slice(3) : ["", "/labadda-staging"];
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const shots = process.env.LABADDA_E2E_SHOTS ?? join(tmpdir(), "labadda-e2e");
mkdirSync(shots, { recursive: true });
const results = [];

async function seen(locator, timeout = 8000) {
  try {
    await locator.first().waitFor({ timeout });
    return true;
  } catch {
    return false;
  }
}

function check(cond, label) {
  results.push({ ok: !!cond, label });
  console.log(`${cond ? "PASS" : "FAIL"}  ${label}`);
  if (!cond) throw new Error(label);
}

async function signIn(browser, base, username) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log(`[${username}] page error: ${e.message}`));
  const external = [];
  page.on("request", (r) => {
    if (!r.url().startsWith(origin) && !r.url().startsWith("data:")) external.push(r.url());
  });
  await page.goto(`${origin}${base}/`);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  const home = await ctx.request.get(`${origin}${base}/api/v1/auth/session`);
  const homeId = (await home.json()).user.home_workspace_id;
  if (homeId) await page.goto(`${origin}${base}/w/${homeId}/noticeboard`);
  return { ctx, page, external };
}

async function wsIdByName(page, base, name) {
  return page.evaluate(
    async ([b, n]) => {
      const r = await fetch(`${b}/api/v1/workspaces`);
      return (await r.json()).workspaces.find((w) => w.name === n)?.id;
    },
    [base, name],
  );
}

async function run(base) {
  const tag = base || "root";
  console.log(`\n== Instance ${tag} ==`);
  const browser = await chromium.launch({ executablePath: process.env.LABADDA_CHROMIUM });
  try {
    // P1: home → division, sibling denied, coherent empty state.
    const ben = await signIn(browser, base, "ben");
    await ben.page.getByRole("heading", { level: 1, name: /Thin Films Section/ }).waitFor();
    check(
      new URL(ben.page.url()).pathname.startsWith(`${base}/w/`),
      `${tag}: lands in home workspace under base path`,
    );
    await ben.page.getByRole("link", { name: "Surface Science Division" }).first().click();
    await ben.page.getByRole("heading", { level: 1, name: /Surface Science Division/ }).waitFor();
    check(
      await seen(ben.page.getByText("Inherited member")),
      `${tag}: division shows inherited access label`,
    );
    check(
      await seen(ben.page.getByText(/No posts yet in Surface Science Division/)),
      `${tag}: coherent empty state`,
    );
    await ben.page.reload();
    await ben.page.getByRole("heading", { level: 1, name: /Surface Science Division/ }).waitFor();
    check(true, `${tag}: deep link survives refresh`);
    const chen = await signIn(browser, base, "chen");
    const sectionB = await wsIdByName(chen.page, base, "Catalysis Section");
    await ben.page.goto(`${origin}${base}/w/${sectionB}/noticeboard`);
    await ben.page.getByRole("heading", { name: "Workspace not available" }).waitFor();
    check(true, `${tag}: sibling section is not available`);

    // P2: post with attachment and due time, persists after reload, excluded from sibling.
    const sectionA = await wsIdByName(ben.page, base, "Thin Films Section");
    await ben.page.goto(`${origin}${base}/w/${sectionA}/noticeboard`);
    check(await seen(ben.page.getByText("Post to Thin Films Section")), `${tag}: composer shows destination`);
    await ben.page.getByLabel("Message").fill("Ellipsometer calibration results attached");
    await ben.page.locator('input[type="datetime-local"]').first().fill("2031-05-01T10:00");
    const pdf = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");
    await ben.page
      .locator('input[type="file"]')
      .setInputFiles({ name: "calibration.pdf", mimeType: "application/pdf", buffer: pdf });
    await ben.page.getByText("calibration.pdf").first().waitFor();
    await ben.page.getByRole("button", { name: "Post", exact: true }).click();
    await ben.page.getByRole("status").filter({ hasText: "Posted" }).waitFor();
    await ben.page.reload();
    await ben.page.locator(".post").filter({ hasText: "Ellipsometer calibration" }).waitFor();
    check(
      await seen(ben.page.getByRole("link", { name: /calibration\.pdf/ })),
      `${tag}: attachment listed after reload`,
    );
    check(
      await seen(ben.page.locator(".secondary").getByText("Ellipsometer calibration")),
      `${tag}: due item in Upcoming`,
    );
    const href = await ben.page.getByRole("link", { name: /calibration\.pdf/ }).getAttribute("href");
    const fileUrl = new URL(href, ben.page.url()).toString();
    check(
      fileUrl.startsWith(`${origin}${base}/api/v1/files/`),
      `${tag}: download stays same-origin under base`,
    );
    const own = await ben.page.evaluate(async (u) => (await fetch(u)).status, fileUrl);
    const sibling = await chen.page.evaluate(async (u) => (await fetch(u)).status, fileUrl);
    check(
      own === 200 && sibling === 404,
      `${tag}: file readable by member (${own}), absent for sibling (${sibling})`,
    );
    await ben.page.screenshot({ path: join(shots, `${tag}-noticeboard.png`) });

    // Collaborative group with a colleague from the sibling section.
    await ben.page.getByRole("link", { name: "+ New group" }).click();
    await ben.page.getByLabel("Group name").fill("Cross-section XPS Club");
    await ben.page.getByLabel("Find colleagues").fill("chen");
    await ben.page.getByRole("button", { name: /\+ Chen Li/ }).click();
    await ben.page.getByRole("button", { name: /Create group with 1 colleague/ }).click();
    await ben.page.getByRole("heading", { level: 1, name: /Cross-section XPS Club/ }).waitFor();
    check(
      await seen(ben.page.getByText("Audience: group members only")),
      `${tag}: group composer shows group-only audience`,
    );
    await chen.page.reload();
    await chen.page.getByRole("link", { name: "Cross-section XPS Club" }).click();
    await chen.page.getByRole("heading", { level: 1, name: /Cross-section XPS Club/ }).waitFor();
    check(true, `${tag}: invited colleague sees the group`);
    const groupId = await wsIdByName(ben.page, base, "Cross-section XPS Club");
    // Live chat in the group.
    await ben.page.goto(`${origin}${base}/w/${groupId}/chat`);
    await chen.page.goto(`${origin}${base}/w/${groupId}/chat`);
    await chen.page.getByText("Live", { exact: true }).waitFor();
    await ben.page.getByText("Live", { exact: true }).waitFor();
    await chen.page.getByLabel("Message Cross-section XPS Club").fill("Spectra uploaded to the share");
    await chen.page.getByRole("button", { name: "Send" }).click();
    try {
      await ben.page
        .locator(".messages")
        .getByText("Spectra uploaded to the share")
        .waitFor({ timeout: 5000 });
    } catch (e) {
      await ben.page.screenshot({ path: join(shots, `${tag}-chat-fail-ben.png`) });
      await chen.page.screenshot({ path: join(shots, `${tag}-chat-fail-chen.png`) });
      throw e;
    }
    check(true, `${tag}: group chat delivered live`);
    const dana = await signIn(browser, base, "dana");
    const danaStatus = await dana.page.evaluate(
      async ([b, id]) => (await fetch(`${b}/api/v1/workspaces/${id}/posts`)).status,
      [base, groupId],
    );
    check(danaStatus === 404, `${tag}: division steward cannot read the group (${danaStatus})`);

    // Whiteboard: draw in one session, converge in another.
    await ben.page.goto(`${origin}${base}/w/${groupId}/board`);
    await chen.page.goto(`${origin}${base}/w/${groupId}/board`);
    await ben.page.getByText("Saved").waitFor();
    await chen.page.locator(".canvas").waitFor();
    const box = await ben.page.locator(".canvas").boundingBox();
    await ben.page.mouse.move(box.x + 100, box.y + 100);
    await ben.page.mouse.down();
    for (let i = 1; i <= 10; i++) await ben.page.mouse.move(box.x + 100 + i * 20, box.y + 100 + i * 8);
    await ben.page.mouse.up();
    await ben.page.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    await chen.page.waitForFunction(
      () => /rev [1-9]/.test(document.querySelector(".toolbar")?.textContent ?? ""),
      null,
      { timeout: 5000 },
    );
    check(true, `${tag}: stroke converged to second session`);
    // Disconnect and reconnect: replay from committed state.
    await chen.ctx.setOffline(true);
    await ben.page.mouse.move(box.x + 300, box.y + 300);
    await ben.page.mouse.down();
    await ben.page.mouse.move(box.x + 360, box.y + 330);
    await ben.page.mouse.up();
    await ben.page.waitForFunction(() => /rev 2/.test(document.querySelector(".toolbar")?.textContent ?? ""));
    await chen.ctx.setOffline(false);
    await chen.page.reload();
    await chen.page.waitForFunction(
      () => /rev 2/.test(document.querySelector(".toolbar")?.textContent ?? ""),
      null,
      { timeout: 8000 },
    );
    check(true, `${tag}: reconnecting session caught up to revision 2`);
    await chen.page.screenshot({ path: join(shots, `${tag}-board.png`) });

    // P3: place an image, then publish a region snapshot from the section board to the parent division.
    await ben.page.goto(`${origin}${base}/w/${sectionA}/board`);
    await ben.page.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAHUlEQVR4nGP4z8BAEhrVMKphVMOohlENIxoGAAD4/H8BWrLzvAAAAABJRU5ErkJggg==",
      "base64",
    );
    await ben.page
      .locator('input[type="file"][aria-label="Image to place on the board"]')
      .setInputFiles({ name: "spectrum.png", mimeType: "image/png", buffer: png });
    await ben.page.waitForFunction(
      () => /rev 1\b/.test(document.querySelector(".toolbar")?.textContent ?? ""),
      null,
      { timeout: 8000 },
    );
    const sbox = await ben.page.locator(".canvas").boundingBox();
    await ben.page.mouse.move(sbox.x + 80, sbox.y + 80);
    await ben.page.mouse.down();
    await ben.page.mouse.move(sbox.x + 260, sbox.y + 200);
    await ben.page.mouse.up();
    await ben.page.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    await ben.page.getByRole("button", { name: "📷 Publish snapshot" }).click();
    const cbox = await ben.page.locator(".canvas").boundingBox();
    await ben.page.mouse.move(cbox.x + 20, cbox.y + 20);
    await ben.page.mouse.down();
    await ben.page.mouse.move(cbox.x + cbox.width * 0.7, cbox.y + cbox.height * 0.7, { steps: 5 });
    await ben.page.mouse.up();
    const dialog = ben.page.getByRole("dialog", { name: "Publish snapshot" });
    await dialog.waitFor();
    check(
      await dialog
        .locator("img.snapshot-preview")
        .evaluate((img) => img.decode().then(() => img.naturalWidth > 0)),
      `${tag}: snapshot preview rendered`,
    );
    await dialog.getByLabel("Post to").selectOption({ label: "Surface Science Division (parent unit)" });
    const publishBtn = dialog.getByRole("button", { name: /Publish to Surface Science Division/ });
    check(await publishBtn.isDisabled(), `${tag}: parent publish blocked until audience confirmed`);
    await dialog.getByRole("checkbox").check();
    await publishBtn.click();
    await dialog.waitFor({ state: "detached" });
    const divisionId = await wsIdByName(ben.page, base, "Surface Science Division");
    await chen.page.goto(`${origin}${base}/w/${divisionId}/noticeboard`);
    await chen.page.getByText(/Board snapshot at revision 2\. Fixed copy/).waitFor();
    check(
      (await chen.page.getByText("Thin Films Section").count()) === 0,
      `${tag}: sibling reader sees the copy without the source name`,
    );
    const snapImg = chen.page.locator(".attachments img").first();
    check(
      await snapImg.evaluate((img) => img.decode().then(() => img.naturalWidth > 0)),
      `${tag}: sibling reader loads the published image`,
    );
    await ben.page.screenshot({ path: join(shots, `${tag}-board-image.png`) });
    await chen.page.screenshot({ path: join(shots, `${tag}-snapshot-in-division.png`) });

    // P4: board-only touch panel (T11, browser-simulated touch).
    await ben.page.goto(`${origin}${base}/w/${sectionA}/board`);
    await ben.page.getByRole("button", { name: "📺 Open on touch panel" }).click();
    const code = (await ben.page.locator(".pair-code").innerText()).trim();
    await ben.page.getByRole("button", { name: "Done" }).click();
    const kiosk = await browser.newContext({ viewport: { width: 1280, height: 800 }, hasTouch: true });
    const panel = await kiosk.newPage();
    const panelExternal = [];
    panel.on("request", (r) => {
      if (!r.url().startsWith(origin) && !r.url().startsWith("data:")) panelExternal.push(r.url());
    });
    await panel.goto(`${origin}${base}/panel`);
    await panel.getByLabel("Panel code").fill(code);
    await panel.getByRole("button", { name: "Open board" }).click();
    await panel.getByRole("button", { name: "End session" }).waitFor();
    check(
      await seen(panel.getByText("Drawing as Ben Okafor")),
      `${tag}: panel opens the chosen board as the pairing user`,
    );
    check(
      (await panel.getByRole("button", { name: "📷 Publish snapshot" }).count()) === 0 &&
        (await panel.getByRole("button", { name: "🖼 Image" }).count()) === 0 &&
        (await panel.getByRole("button", { name: "Create task from board", exact: true }).count()) === 0,
      `${tag}: panel hides publishing, file picker and task creation`,
    );
    await panel.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    const revBefore = await ben.page.evaluate(() =>
      Number((document.querySelector(".toolbar")?.textContent ?? "").match(/rev (\d+)/)?.[1] ?? 0),
    );
    const pbox = await panel.locator(".canvas").boundingBox();
    const cdp = await kiosk.newCDPSession(panel);
    const pt = (i) => ({ x: pbox.x + 200 + i * 25, y: pbox.y + 150 + i * 10 });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [pt(0)] });
    for (let i = 1; i <= 12; i++)
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [pt(i)] });
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await panel.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    await ben.page.waitForFunction(
      (r) => Number((document.querySelector(".toolbar")?.textContent ?? "").match(/rev (\d+)/)?.[1] ?? 0) > r,
      revBefore,
      { timeout: 8000 },
    );
    check(true, `${tag}: touch stroke on the panel reaches the desktop board`);
    await panel.screenshot({ path: join(shots, `${tag}-panel.png`) });
    const probes = await panel.evaluate(
      async ([b, div]) => {
        const st = async (u, h = {}) => (await fetch(u, { headers: h })).status;
        const P = { "X-LabAdda-Panel": "1" };
        return [
          await st(`${b}/api/v1/notes`),
          await st(`${b}/api/v1/notes`, P),
          await st(`${b}/api/v1/workspaces`, P),
          await st(`${b}/api/v1/admin/users`, P),
          await st(`${b}/api/v1/workspaces/${div}/board`, P),
        ];
      },
      [base, divisionId],
    );
    check(
      JSON.stringify(probes) === JSON.stringify([401, 401, 401, 401, 404]),
      `${tag}: panel cannot reach notes, workspaces, admin or other boards (${probes})`,
    );
    await panel.goto(`${origin}${base}/w/${sectionA}/noticeboard`);
    check(
      await seen(panel.getByLabel("Username")),
      `${tag}: desktop pages on the panel ask for a normal sign-in`,
    );
    await panel.goto(`${origin}${base}/panel`);
    await panel.getByRole("button", { name: "End session" }).click();
    await panel.getByText("Session ended. The board was cleared").waitFor();
    check((await panel.locator(".canvas").count()) === 0, `${tag}: ending clears the board from the panel`);
    const after = await panel.evaluate(
      async (b) => (await fetch(`${b}/api/v1/panel/session`, { headers: { "X-LabAdda-Panel": "1" } })).status,
      base,
    );
    check(after === 401, `${tag}: ended panel session is unusable (${after})`);
    // Idle lock (test stack uses a 35 s idle window).
    await ben.page.getByRole("button", { name: "📺 Open on touch panel" }).click();
    const code2 = (await ben.page.locator(".pair-code").innerText()).trim();
    await ben.page.getByRole("button", { name: "Done" }).click();
    await panel.getByLabel("Panel code").fill(code2);
    await panel.getByRole("button", { name: "Open board" }).click();
    await panel.getByRole("button", { name: "End session" }).waitFor();
    await panel.getByText(/Locking in \d+ s/).waitFor({ timeout: 40000 });
    await panel.getByText("Panel locked after inactivity").waitFor({ timeout: 40000 });
    check((await panel.locator(".canvas").count()) === 0, `${tag}: idle panel locks and clears the board`);
    check(panelExternal.length === 0, `${tag}: panel makes no external requests`);
    await kiosk.close();

    // My Notes stays private.
    await ben.page.goto(`${origin}${base}/notes`);
    await ben.page.getByLabel("Title").fill("Order argon cylinders");
    await ben.page.getByRole("button", { name: "Add note" }).click();
    await ben.page.getByRole("heading", { name: "Order argon cylinders" }).waitFor();
    const noteId = await ben.page.evaluate(
      async (b) => (await (await fetch(`${b}/api/v1/notes`)).json()).notes[0].id,
      base,
    );
    const admin = await signIn(browser, base, "admin");
    const adminNote = await admin.page.evaluate(
      async ([b, id]) => (await fetch(`${b}/api/v1/notes/${id}`)).status,
      [base, noteId],
    );
    check(adminNote === 404, `${tag}: administrator cannot open a personal note (${adminNote})`);

    for (const s of [ben, chen, dana, admin])
      check(s.external.length === 0, `${tag}: no external requests (${s.external.join(", ") || "none"})`);
    // Logging out of this instance leaves the other instance's cookie intact (checked in the next instance run).
    await admin.ctx.close();
  } finally {
    await browser.close();
  }
}

async function crossInstance() {
  if (bases.length < 2) return;
  const browser = await chromium.launch({ executablePath: process.env.LABADDA_CHROMIUM });
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  for (const base of bases) {
    await page.goto(`${origin}${base}/`);
    await page.getByLabel("Username").fill("asha");
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  }
  // Signs out of the last instance only.
  await page.getByRole("button", { name: /^Account menu for / }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await page.getByLabel("Username").waitFor();
  const firstStatus = await page.evaluate(
    async (b) => (await fetch(`${b}/api/v1/auth/session`)).status,
    bases[0],
  );
  check(
    firstStatus === 200,
    `cross-instance: signing out of ${bases[1]} keeps ${bases[0] || "root"} signed in`,
  );
  await browser.close();
}

let failed = false;
for (const base of bases) {
  try {
    await run(base);
  } catch (e) {
    failed = true;
    console.log(`ERROR ${e.message}`);
  }
}
try {
  await crossInstance();
} catch (e) {
  failed = true;
  console.log(`ERROR ${e.message}`);
}
writeFileSync(join(shots, "results.json"), JSON.stringify(results, null, 2));
console.log(`\n${results.filter((r) => r.ok).length}/${results.length} checks passed. Screenshots: ${shots}`);
process.exit(failed ? 1 : 0);
