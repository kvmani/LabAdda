// Fresh local synthetic proxy stack: capacity proposals and non-authorizing previews.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const axe = require.resolve("../frontend/node_modules/axe-core/axe.min.js");
const out = process.argv[2] ?? "/tmp/labadda-capacity-proposals";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
const origin = "http://127.0.0.1:8080";
let checks = 0;
function check(value, label) {
  assert.ok(value, label);
  checks++;
  console.log("PASS " + label);
}
async function login(base, user) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }),
    page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return { ctx, page, session };
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin"),
      ben = await login(base, "ben"),
      api = origin + base + "/api/v1";
    const headers = { "X-CSRF-Token": admin.session.csrf_token };
    const legacy = await admin.ctx.request.post(api + "/admin/policy-drafts", {
      headers,
      data: { base_revision: 0, reason: "Synthetic legacy revision", profile: {} },
    });
    assert.equal(legacy.status(), 201);
    const before = await (await ben.ctx.request.get(api + "/usage")).json();
    await admin.page.goto(origin + base + "/admin/storage");
    await admin.page.getByRole("heading", { name: "Site proposal revision 1" }).waitFor();
    check(
      await admin.page.getByText("Not recorded in version 1", { exact: true }).isVisible(),
      base + ": legacy history has explicit missing capacity fields",
    );
    const site = admin.page.getByLabel("Proposed site asset budget (MiB; blank means not configured)");
    const percent = admin.page.getByLabel("Proposed filesystem reserve (%)");
    await site.fill("10240");
    await admin.page.getByRole("button", { name: "Preview proposed capacity", exact: true }).click();
    const preview = admin.page.getByRole("region", { name: "Capacity preview", exact: true });
    await preview.waitFor();
    check(
      await preview.getByRole("heading", { name: "Capacity preview (incomplete)" }).isVisible(),
      base + ": preview remains explicitly incomplete",
    );
    check(
      (await preview.innerText()).includes("Headroom is an upper bound"),
      base + ": headroom cannot be mistaken for guaranteed free space",
    );
    await preview.scrollIntoViewIfNeeded();
    await admin.page.screenshot({ path: out + (base ? "/preview-prefix.png" : "/preview-root.png") });
    await percent.fill("11");
    check((await preview.count()) === 0, base + ": editing profile clears prior preview");

    let release, entered;
    const gate = new Promise((r) => {
        release = r;
      }),
      arrived = new Promise((r) => {
        entered = r;
      });
    await admin.page.route(
      api + "/admin/capacity-forecasts",
      async (route) => {
        const response = await route.fetch();
        entered();
        await gate;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    await admin.page.getByRole("button", { name: "Preview proposed capacity", exact: true }).click();
    await arrived;
    await percent.fill("12");
    release();
    await admin.page
      .getByRole("button", { name: "Preview proposed capacity", exact: true })
      .waitFor({ state: "visible" });
    await admin.page.waitForFunction(() =>
      [...document.querySelectorAll("button")].some(
        (b) => b.textContent === "Preview proposed capacity" && !b.disabled,
      ),
    );
    check((await preview.count()) === 0, base + ": late response cannot revive preview for edited inputs");
    await admin.page.getByRole("button", { name: "Preview proposed capacity", exact: true }).click();
    await preview.waitFor();
    await admin.page.getByRole("button", { name: "Reload observations", exact: true }).click();
    await admin.page.getByText("Observations refreshed.", { exact: true }).waitFor();
    check((await preview.count()) === 0, base + ": refreshed observations clear old capacity preview");
    await admin.page.getByLabel("Proposal reason").fill("Synthetic site capacity review");
    await admin.page.getByRole("button", { name: "Save non-enforcing proposal", exact: true }).click();
    await admin.page.getByRole("heading", { name: "Site proposal revision 2" }).waitFor();
    const history = await (await admin.ctx.request.get(api + "/admin/policy-drafts")).json();
    check(
      history.drafts[0].schema_version === 2 &&
        history.drafts[0].profile.site_asset_budget_bytes === 10 * 1024 ** 3 &&
        !history.drafts[0].enforced,
      base + ": immutable capacity proposal saved without activation",
    );
    check(history.drafts[1].schema_version === 1, base + ": old proposal remains version one");
    const after = await (await ben.ctx.request.get(api + "/usage")).json();
    check(after.runtime_limit.bytes === before.runtime_limit.bytes, base + ": current pilot limit unchanged");
    check(
      (
        await ben.ctx.request.post(api + "/admin/capacity-forecasts", {
          headers: { "X-CSRF-Token": ben.session.csrf_token },
          data: { profile: { schema_version: 2 } },
        })
      ).status() === 403,
      base + ": member cannot preview policy capacity",
    );
    await admin.page.getByRole("button", { name: "Preview proposed capacity", exact: true }).click();
    await preview.waitFor();
    await admin.page.setViewportSize({ width: 390, height: 844 });
    await preview.scrollIntoViewIfNeeded();
    check(
      await admin.page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      base + ": capacity form fits mobile without page overflow",
    );
    await admin.page.addScriptTag({ path: axe });
    const violations = await admin.page.evaluate(async () =>
      (
        await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
        })
      ).violations.map((v) => v.id),
    );
    check(violations.length === 0, base + ": mobile admin has no axe findings " + JSON.stringify(violations));
    const historyRegion = admin.page.getByRole("region", { name: "Recent immutable proposals", exact: true });
    await historyRegion.focus();
    await historyRegion.press("ArrowRight");
    await historyRegion.evaluate((e) => e.scrollLeft > 0 || new Promise((r) => setTimeout(r, 300)));
    check(
      await historyRegion.evaluate((e) => e.scrollLeft > 0),
      base + ": proposal history scrolls sideways",
    );
    check(
      await historyRegion.evaluate((e) => e === document.activeElement),
      base + ": proposal history supports keyboard scrolling",
    );
    await preview.scrollIntoViewIfNeeded();
    await admin.page.screenshot({
      path: out + (base ? "/preview-prefix-mobile.png" : "/preview-root-mobile.png"),
    });
    await admin.ctx.close();
    await ben.ctx.close();
  }
  console.log(`${checks} capacity proposal browser checks passed`);
} finally {
  await browser.close();
}
