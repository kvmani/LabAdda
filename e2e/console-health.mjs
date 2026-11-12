// A4 system health and events: forced degraded state, guidance link, acknowledge, axe at / and /labadda-staging.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-console-health";
mkdirSync(output, { recursive: true });
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
// The test-only force file (read only in test environments) lives in each instance's asset directory.
const forceFiles = ["root", "staging"].map(
  (name) => `${root}var/proxy-stack/${name}/assets/.test-health-force`,
);
function force(text) {
  for (const file of forceFiles) {
    mkdirSync(dirname(file), { recursive: true });
    if (text) writeFileSync(file, text);
    else rmSync(file, { force: true });
  }
}
force("jobs=degraded");
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
async function login(base) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/");
  console.log(await page.title(), (await page.locator("body").innerText()).slice(0, 200));
  await page.getByLabel("Username", { exact: true }).fill("admin");
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
}
async function health(page, base, tag) {
  await page.goto(origin + base + "/admin/health");
  const card = page.locator("section.ui-card", {
    has: page.getByRole("heading", { name: "Background jobs" }),
  });
  await card.getByText("Degraded", { exact: true }).waitFor({ timeout: 30000 });
  check(true, base + " forced degraded item is shown within one poll");
  await page.getByText(/checks? needs? attention/).waitFor();
  check((await card.getByText(/^Checked /).count()) === 1, base + " card says when it was checked");
  const backups = page.locator("section.ui-card", { has: page.getByRole("heading", { name: "Backups" }) });
  check(
    (await backups.getByText("Unknown", { exact: true }).count()) === 1,
    base + " missing backup report is unknown",
  );
  check((await backups.getByText("Not measured").count()) === 1, base + " unknown shows no figure");
  const link = page.getByRole("link", { name: "What to do: Background jobs" });
  check(
    (await link.getAttribute("href")).endsWith("/help/troubleshooting/health-background-jobs"),
    base + " guidance link",
  );
  await page
    .getByRole("img", { name: /Database, last 24 hours/ })
    .first()
    .waitFor({ timeout: 15000 })
    .catch(() => {});
  await page.screenshot({ path: `${output}/health-${tag}.png`, fullPage: true });
  for (const width of [1400, 390]) await audit(page, width, base + " health");
  await page.setViewportSize({ width: 1400, height: 1100 });
  await link.click();
  await page.getByRole("heading", { name: "Background job problems", level: 1 }).waitFor();
  check(true, base + " guidance page opens");
}
async function events(page, base, tag) {
  await page.goto(origin + base + "/admin/events");
  await page.getByRole("table", { name: "Operational events, newest first" }).waitFor();
  const open = page.getByRole("button", { name: /Open details: Background jobs is degraded/ }).first();
  for (let attempt = 0; attempt < 10 && !(await open.count()); attempt++) {
    await page.waitForTimeout(3000);
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
  }
  await open.click();
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await page.getByText("Write a short note").waitFor();
  check(true, base + " acknowledging needs a note");
  await page.getByLabel("Note").fill("Operator informed.");
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await page.getByText("Operator informed.").waitFor();
  check(true, base + " acknowledged with a note");
  await page.screenshot({ path: `${output}/events-${tag}.png` });
  for (const width of [1400, 390]) await audit(page, width, base + " events");
  await page.setViewportSize({ width: 1400, height: 1100 });
  await page.getByRole("button", { name: "Close panel" }).click();
  await page.getByRole("combobox", { name: "Status" }).selectOption("acknowledged");
  await page
    .getByRole("button", { name: /Open details: Background jobs is degraded/ })
    .first()
    .waitFor();
  check(new URL(page.url()).searchParams.get("state") === "acknowledged", base + " filter lives in the URL");
  await page.goto(origin + base + "/admin/health");
  const card = page.locator("section.ui-card", {
    has: page.getByRole("heading", { name: "Background jobs" }),
  });
  await card.getByText("Degraded", { exact: true }).waitFor();
  check(true, base + " acknowledged item stays degraded");
  force("");
  await card.getByText("Healthy", { exact: true }).waitFor({ timeout: 40000 });
  check(true, base + " recovered item turns healthy within a poll");
  await page.goto(origin + base + "/admin/events?state=resolved");
  await page
    .getByRole("button", { name: /Open details: Background jobs is degraded/ })
    .first()
    .waitFor();
  check(true, base + " recovery resolved the event");
}
try {
  for (const [base, tag] of [
    ["", "root"],
    ["/labadda-staging", "prefix"],
  ]) {
    force("jobs=degraded");
    const admin = await login(base);
    try {
      await health(admin.page, base, tag);
      await events(admin.page, base, tag);
    } finally {
      await admin.context.close();
    }
  }
  force("");
  console.log(`${checks} console health browser checks passed`);
} finally {
  await browser.close();
}
