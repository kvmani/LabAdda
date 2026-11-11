// Requires fresh proxy-stack fixtures; may follow governance.mjs.
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const origin = "http://127.0.0.1:8080";
const out = process.argv[2] ?? "/tmp/labadda-capabilities";
mkdirSync(out, { recursive: true });
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let passed = 0;
function check(value, name) {
  assert.ok(value, name);
  console.log("PASS " + name);
  passed++;
}
async function login(base, user) {
  const ctx = await browser.newContext({
    viewport: { width: 1400, height: 1100 },
    timezoneId: "Asia/Kolkata",
  });
  const page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { ctx, page };
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin"),
      ben = await login(base, "ben");
    await ben.page.goto(origin + base + "/operations");
    await ben.page.waitForURL((url) => !/\/(admin|operations)(\/|$)/.test(url.pathname));
    check(true, base + ": observer access starts denied");
    await admin.page.goto(origin + base + "/admin/settings");
    await admin.page.getByLabel("Operational reader account").selectOption({ label: "ben" });
    await admin.page.getByLabel("Access change reason").fill("Synthetic storage observation walkthrough");
    await admin.page.getByLabel("Confirm administrator password").fill("incorrect-fixture-password");
    await admin.page.getByRole("button", { name: "Grant operational read access" }).click();
    await admin.page.getByRole("alert").filter({ hasText: "Password confirmation failed" }).waitFor();
    check(
      (await ben.ctx.request.get(origin + base + "/api/v1/admin/usage")).status() === 403,
      base + ": incorrect password grants nothing",
    );
    await admin.page.getByLabel("Confirm administrator password").fill(password);
    await admin.page.getByRole("button", { name: "Grant operational read access" }).click();
    await admin.page.getByText("Time-limited operational read access granted.", { exact: true }).waitFor();
    check(
      (await admin.page.getByLabel("Confirm administrator password").inputValue()) === "",
      base + ": password cleared after operation",
    );
    await ben.page.goto(origin + base + "/operations");
    await ben.page.getByRole("heading", { name: "Partial site measurement" }).waitFor();
    await ben.page.screenshot({
      path: out + (base ? "/observer-prefix.png" : "/observer-root.png"),
      fullPage: true,
    });
    check(true, base + ": granted observer reads operational metadata");
    check(
      (await ben.ctx.request.get(origin + base + "/api/v1/admin/users")).status() === 403 &&
        (await ben.ctx.request.get(origin + base + "/api/v1/admin/policy-drafts")).status() === 403,
      base + ": observer cannot administer identities or policies",
    );
    await admin.page.getByLabel("Confirm administrator password").fill(password);
    await admin.page.getByRole("button", { name: "Revoke selected account", exact: true }).click();
    await admin.page.getByText("Operational access revoked.", { exact: true }).waitFor();
    await ben.page.getByRole("button", { name: "Refresh operational observations" }).click();
    await ben.page.getByRole("alert").filter({ hasText: "Operational read access is required" }).waitFor();
    check(
      (await ben.page.getByRole("heading", { name: "Partial site measurement" }).count()) === 0,
      base + ": revoked refresh clears measurement and is refused",
    );
    await ben.ctx.close();
    await admin.ctx.close();
  }
  console.log(`${passed} capability browser checks passed`);
} finally {
  await browser.close();
}
