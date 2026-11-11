// Requires fresh disposable proxy stack and inventory-jobs-fixture.py for both databases.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const output = process.argv[2] ?? "/tmp/labadda-inventory-jobs";
mkdirSync(output, { recursive: true });
const origin = "http://127.0.0.1:8080";
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(ok, message) {
  assert.ok(ok, message);
  checks++;
  console.log("PASS " + message);
}
async function login(base, username) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { ctx, page };
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    await admin.page.goto(origin + base + "/admin");
    const region = admin.page.getByRole("region", { name: "Inventory jobs", exact: true });
    await region.getByRole("button", { name: "Older inventory jobs" }).waitFor();
    const first = await region.getByRole("button", { name: /View attempts for/ }).allTextContents();
    check(first.length === 10, base + " bounded first page");
    await region.getByRole("button", { name: "Older inventory jobs" }).click();
    await region
      .getByRole("button", { name: /View attempts for/ })
      .first()
      .waitFor();
    const second = await region.getByRole("button", { name: /View attempts for/ }).allTextContents();
    check(
      second.length === 6 && second.every((x) => !first.includes(x)),
      base + " older page without duplicates",
    );
    await region.getByLabel("Inventory job state").selectOption("completed");
    await region.getByRole("button", { name: /View attempts for/ }).click();
    await region
      .getByText(/Accepted receipt:/)
      .first()
      .waitFor();
    check(
      (await region.getByText(/Attempt 1: failed/).count()) === 1 &&
        (await region.getByText(/Attempt 2: completed/).count()) === 1,
      base + " immutable retry history visible",
    );
    await region.getByLabel("Inventory job state").selectOption("running");
    await region.getByRole("button", { name: /View attempts for/ }).click();
    await region.getByText(/A running label does not prove an active worker/).waitFor();
    check(true, base + " expired lease is not shown as healthy");
    check(
      (await region.getByRole("button", { name: /^Run|^Retry|^Cancel|^Delete/ }).count()) === 0,
      base + " no web mutation controls",
    );
    for (const width of [1400, 390]) {
      await admin.page.setViewportSize({ width, height: 1100 });
      await region.scrollIntoViewIfNeeded();
      await admin.page.addScriptTag({
        path: require.resolve("../frontend/node_modules/axe-core/axe.min.js"),
      });
      const violations = await admin.page.evaluate(async () =>
        (
          await window.axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
          })
        ).violations.map((x) => x.id),
      );
      check(violations.length === 0, base + " axe " + width + " " + violations.join(","));
      check(
        await admin.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        base + " no overflow " + width,
      );
      await admin.page.screenshot({ path: output + "/" + (base ? "prefix" : "root") + "-" + width + ".png" });
    }
    // A delayed detail response must not repopulate the view after the filter changes.
    let release, entered;
    const waiting = new Promise((resolve) => {
      entered = resolve;
    });
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    await admin.page.route(
      "**/api/v1/admin/inventory-jobs/*",
      async (route) => {
        const response = await route.fetch();
        entered();
        await gate;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    await region.getByRole("button", { name: /View attempts for/ }).click();
    await waiting;
    await region.getByLabel("Inventory job state").selectOption("queued");
    await region.getByRole("button", { name: "Older inventory jobs" }).waitFor();
    const responseDone = admin.page.waitForResponse((r) => /inventory-jobs\/[a-f0-9-]+$/.test(r.url()));
    release();
    await responseDone;
    await admin.page.waitForTimeout(100);
    check(
      (await region.getByRole("heading", { name: "Selected inventory job" }).count()) === 0,
      base + " delayed detail discarded after filter change",
    );
    await admin.page.setViewportSize({ width: 1400, height: 1100 });
    await admin.page.getByLabel("Operational reader account").selectOption({ label: "ben" });
    await admin.page.getByLabel("Access change reason").fill("Synthetic inventory job walkthrough");
    await admin.page.getByLabel("Confirm administrator password").fill(password);
    await admin.page.getByRole("button", { name: "Grant operational read access" }).click();
    await admin.page.getByText("Time-limited operational read access granted.", { exact: true }).waitFor();
    const observer = await login(base, "ben");
    await observer.page.goto(origin + base + "/operations");
    const observed = observer.page.getByRole("region", { name: "Inventory jobs", exact: true });
    await observed
      .getByRole("button", { name: /View attempts for/ })
      .first()
      .waitFor();
    check(true, base + " delegated operational reader sees jobs");
    await admin.page.getByLabel("Confirm administrator password").fill(password);
    await admin.page.getByRole("button", { name: "Revoke selected account", exact: true }).click();
    await admin.page.getByText("Operational access revoked.", { exact: true }).waitFor();
    await observed.getByRole("button", { name: "Refresh inventory jobs" }).click();
    await observed.getByRole("alert").waitFor();
    check(
      (await observed.getByRole("button", { name: /View attempts for/ }).count()) === 0,
      base + " denied refresh clears job data",
    );
    await observer.ctx.close();
    await admin.ctx.close();
  }
  console.log(`${checks} inventory job browser checks passed`);
} finally {
  await browser.close();
}
