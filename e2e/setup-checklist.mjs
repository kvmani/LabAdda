// H3 setup checklist at / and /labadda-staging: live states, links, access.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-setup-checklist";
mkdirSync(output, { recursive: true });
const runDirectory = process.env.LABADDA_RUN_DIR ?? root + "var/proxy-stack";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
const statusFile = (base) => runDirectory + (base ? "/staging" : "/root") + "/status/backup-status.json";
function receipt(base, hoursAgo, changes = {}) {
  const finished = new Date(Date.now() - hoursAgo * 3600_000).toISOString().replace(/\.\d+Z$/, "Z");
  writeFileSync(
    statusFile(base),
    JSON.stringify({
      format: 1,
      finished_at: finished,
      result: "success",
      size_bytes: 4096,
      verification: "passed",
      destination: "nas-room",
      schema: "0029",
      release: "r1",
      ...changes,
    }),
  );
}
async function login(base, username) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { context, page };
}
async function audit(page, width, label) {
  await page.setViewportSize({ width, height: 1100 });
  await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((item) => item.id),
  );
  check(violations.length === 0, `${label} accessibility ${width}: ${violations}`);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}`,
  );
  await page.setViewportSize({ width: 1400, height: 1100 });
}
async function checkChecklist(admin, base) {
  const { page } = admin;
  const label = base + " setup checklist";
  rmSync(statusFile(base), { force: true });
  await page.goto(origin + base + "/admin");
  await page.getByRole("link", { name: "Help for administrators", exact: true }).click();
  await page.waitForURL(/\/admin\/help\/setup$/);
  await page.getByRole("heading", { name: "Setting up this site", exact: true }).waitFor();
  const items = page.getByRole("list", { name: "Setup checklist" }).getByRole("listitem");
  check((await items.count()) === 7, label + " lists seven items");
  check((await page.getByRole("checkbox").count()) === 0, label + " has nothing to tick");
  const backups = items.filter({ hasText: "Backups reporting healthy" });
  check(
    (await backups.getByText("Unknown", { exact: true }).count()) === 1,
    label + " missing backup is unknown",
  );
  const restore = items.filter({ hasText: "A test restore recorded" });
  check(
    (await restore.getByText("Unknown", { exact: true }).count()) === 1,
    label + " test restore is unknown",
  );
  receipt(base, 1);
  await page.getByRole("button", { name: "Check again", exact: true }).click();
  await backups.getByText("Done", { exact: true }).waitFor();
  check(true, label + " a fresh verified backup turns the line done");
  receipt(base, 60);
  await page.getByRole("button", { name: "Check again", exact: true }).click();
  await backups.getByText("Not done", { exact: true }).waitFor();
  check(true, label + " an old backup turns it back to not done");
  receipt(base, 1);
  await audit(page, 1400, label);
  await audit(page, 390, label);
  await page.screenshot({ path: output + (base ? "/prefix-setup.png" : "/root-setup.png"), fullPage: true });
  await items
    .first()
    .getByRole("link", { name: /^Open the page/ })
    .click();
  await page.waitForURL(/\/admin\/people$/);
  check(true, label + " links to the screen that fixes the line");
  await page.goBack();
  await items
    .first()
    .getByRole("link", { name: /^Read the help/ })
    .click();
  await page.getByRole("heading", { name: "Adding a person" }).waitFor();
  check(true, label + " links to the help page");
  const text = await page.locator("main").innerText();
  check(!text.includes("proxy-stack") && !text.includes("backup-status"), label + " shows no path");
}

async function checkMember(member, base) {
  const label = base + " member";
  const response = await member.context.request.get(origin + base + "/api/v1/admin/setup-checklist");
  check(response.status() === 403, label + " cannot read the checklist");
}

for (const base of ["", "/labadda-staging"]) {
  const admin = await login(base, "admin");
  const member = await login(base, "ben");
  await checkChecklist(admin, base);
  await checkMember(member, base);
  await admin.context.close();
  await member.context.close();
}
await browser.close();
console.log(`setup-checklist: ${checks} checks passed`);
