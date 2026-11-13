// A7 Backups page, read-only settings and the site notice at / and /labadda-staging.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-console-backups";
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
function localValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

async function checkBackups(admin, base) {
  const { page } = admin;
  const label = base + " backups";
  rmSync(statusFile(base), { force: true });
  await page.goto(origin + base + "/admin/backups");
  await page.getByRole("heading", { name: "Backups", exact: true }).waitFor();
  await page.getByText("No backup has been recorded.").waitFor();
  check(await page.getByText("Unknown", { exact: true }).isVisible(), label + " missing receipt is unknown");
  check((await page.getByText("Verification", { exact: true }).count()) === 0, label + " implies no backup");
  await audit(page, 1400, label + " unknown");
  receipt(base, 1);
  await page.getByRole("button", { name: "Check again", exact: true }).click();
  await page.getByText("Healthy", { exact: true }).waitFor();
  check(await page.getByText("nas-room", { exact: true }).isVisible(), label + " shows destination alias");
  check(await page.getByText("Passed", { exact: true }).isVisible(), label + " shows verification");
  check(await page.getByText("4 KiB", { exact: true }).isVisible(), label + " shows size");
  check(
    await page.getByText("Not recorded. The server does not report its timer to this page.").isVisible(),
    label + " says next run is not recorded",
  );
  await audit(page, 1400, label + " healthy");
  await audit(page, 390, label + " healthy");
  await page.screenshot({
    path: output + (base ? "/prefix-backups.png" : "/root-backups.png"),
    fullPage: true,
  });
  receipt(base, 60);
  await page.getByRole("button", { name: "Check again", exact: true }).click();
  await page.getByText("Stale", { exact: true }).waitFor();
  check(true, label + " old receipt is stale");
  writeFileSync(statusFile(base), "{ this is not json");
  await page.getByRole("button", { name: "Check again", exact: true }).click();
  await page.getByText("The backup record cannot be read.").waitFor();
  const text = await page.locator("main").innerText();
  check(!text.includes("proxy-stack") && !text.includes("backup-status"), label + " shows no path");
  receipt(base, 1);
}

async function checkSettings(admin, member, base) {
  const { page } = admin;
  const label = base + " settings";
  await page.goto(origin + base + "/admin/settings");
  await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
  await page.getByRole("heading", { name: "Site notice", exact: true }).waitFor();
  await page.getByRole("heading", { name: "Signing in", exact: true }).waitFor();
  const text = await page.locator("main").innerText();
  check(
    text.includes("Changed by the operator in the site configuration file."),
    label + " names who changes",
  );
  check(
    !/postgresql|labadda_e2e|proxy-stack|labadda-dev|127\.0\.0\.1/.test(text),
    label + " shows no path or host",
  );
  const markup = "<b>Maintenance at six</b>";
  await page.getByLabel(/Notice text/).fill(markup);
  await page.getByLabel("Notice level", { exact: true }).selectOption("warning");
  await page.getByLabel(/Show until/).fill(localValue(new Date(Date.now() + 86400_000)));
  await page.getByRole("button", { name: "Publish notice", exact: true }).click();
  const outcome = page.getByText("The site notice was published.").or(page.locator("main [role=alert]"));
  await outcome.first().waitFor();
  check(
    await page.getByText("The site notice was published.").isVisible(),
    label + " publishes: " + (await outcome.first().innerText()),
  );
  await page.goto(origin + base + "/admin/settings");
  const banner = page.getByRole("status").filter({ hasText: "Maintenance at six" }).first();
  await banner.waitFor();
  check((await banner.innerText()).includes(markup), label + " banner shows markup as typed");
  check((await page.locator(".shell-notice b").count()) === 0, label + " banner is escaped");
  await audit(page, 1400, label + " with notice");
  await audit(page, 390, label + " with notice");
  await page.screenshot({
    path: output + (base ? "/prefix-settings.png" : "/root-settings.png"),
    fullPage: true,
  });
  await member.page.goto(origin + base + "/");
  await member.page.locator(".shell-notice").getByText("Maintenance at six").waitFor();
  check(true, label + " every signed-in person sees the notice");
  await page.getByRole("button", { name: "Remove notice", exact: true }).click();
  await page.getByText("The site notice was removed.").waitFor();
  await member.page.goto(origin + base + "/");
  await member.page.getByRole("button", { name: /^Account menu for / }).waitFor();
  check((await member.page.locator(".shell-notice").count()) === 0, label + " removed notice disappears");
}

async function checkMember(member, base) {
  const label = base + " member";
  const endpoint = origin + base + "/api/v1";
  check(
    (await member.context.request.get(endpoint + "/admin/backups/status")).status() === 403,
    label + " no backups",
  );
  check(
    (await member.context.request.get(endpoint + "/admin/settings")).status() === 403,
    label + " no settings",
  );
  check(
    (await member.context.request.get(endpoint + "/site/banner")).status() === 200,
    label + " can read banner",
  );
}

for (const base of ["", "/labadda-staging"]) {
  const admin = await login(base, "admin");
  const member = await login(base, "bharat");
  await checkBackups(admin, base);
  await checkSettings(admin, member, base);
  await checkMember(member, base);
  await admin.context.close();
  await member.context.close();
}
await browser.close();
console.log(`console-backups: ${checks} checks passed`);
