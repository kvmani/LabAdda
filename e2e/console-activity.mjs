// A5 Activity page at / and /labadda-staging: tiles, charts, protected unit figures and export.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-console-activity";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
function seed(base) {
  execFileSync(root + ".venv/bin/python", [root + "e2e/activity-fixture.py"], {
    cwd: root,
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ?? root + "backend",
      LABADDA_ENV: "test",
      LABADDA_DATABASE_URL:
        "postgresql+psycopg://labadda:labadda-dev@localhost:5432/" +
        (base ? "labadda_e2e_prefix" : "labadda_e2e_root"),
    },
    stdio: "pipe",
  });
}
async function login(base, username) {
  const context = await browser.newContext({
    viewport: { width: 1400, height: 1100 },
    acceptDownloads: true,
  });
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

async function checkAdministrator(admin, base) {
  const { page } = admin;
  const label = base + " activity";
  await page.goto(origin + base + "/admin/activity");
  await page.getByRole("heading", { name: "Activity", exact: true }).waitFor();
  await page.getByText("Active people in the last 7 days", { exact: true }).waitFor();
  check(
    (await page.getByLabel("Period", { exact: true }).inputValue()) === "30d",
    label + " defaults to 30 days",
  );
  check(
    await page.getByText("Peak simultaneous connections", { exact: true }).isVisible(),
    label + " peak tile",
  );
  for (const title of [
    "Active people per day",
    "Activity by feature",
    "Activity by weekday and hour",
    "Storage growth",
    "Uploads by size",
    "Active people by unit",
  ]) {
    check((await page.getByText(title, { exact: true }).count()) > 0, `${label} shows ${title}`);
  }
  const units = page.getByRole("table", { name: "All units" });
  const corrosion = units.getByRole("row").filter({ hasText: "Corrosion Section" });
  check((await corrosion.innerText()).includes("Fewer than 5"), label + " small unit is suppressed");
  const films = units.getByRole("row").filter({ hasText: "Thin Films Section" });
  check(/\b5\b/.test(await films.innerText()), label + " published unit is rounded");
  const text = await page.locator("main").innerText();
  check(
    !text.includes("Project Tejas") && !text.includes("Microscopy Journal Club"),
    label + " names no project or group",
  );
  check(text.includes("Projects") && text.includes("Groups"), label + " shows project and group totals");
  await page.getByRole("button", { name: "View as table" }).first().click();
  await page.getByRole("table", { name: /Active people per day/ }).waitFor();
  check(true, label + " chart opens as a table");
  await audit(page, 1400, label);
  await audit(page, 390, label);
  await page.screenshot({
    path: output + (base ? "/prefix-activity.png" : "/root-activity.png"),
    fullPage: true,
  });
  await page.getByLabel("Period", { exact: true }).selectOption("7d");
  await page.waitForURL(/period=7d/);
  await page
    .getByText(/Last 7 days \(/)
    .first()
    .waitFor();
  check(true, label + " period kept in the address");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export figures", exact: true }).click();
  check((await download).suggestedFilename() === "activity-7d.csv", label + " exports CSV");
  await page.getByText("Report prepared. The export itself is recorded in the audit trail.").waitFor();
  const trail = await admin.context.request.get(origin + base + "/api/v1/admin/audit?group=exports");
  check(JSON.stringify(await trail.json()).includes("analytics.export"), label + " export is audited");
}

async function checkReader(reader, base) {
  const { page } = reader;
  const label = base + " usage reader";
  await page.goto(origin + base + "/admin/activity?period=90d");
  await page.getByRole("heading", { name: "Activity", exact: true }).waitFor();
  await page.getByText("Active people in the last 30 days", { exact: true }).waitFor();
  check(
    (await page.getByLabel("Period", { exact: true }).inputValue()) === "90d",
    label + " deep link period",
  );
}

async function checkMember(member, base) {
  const label = base + " member";
  const endpoint = origin + base + "/api/v1/admin/analytics";
  for (const path of ["/summary", "/units", "/export.csv"]) {
    check((await member.context.request.get(endpoint + path)).status() === 403, `${label} refused ${path}`);
  }
  await member.page.goto(origin + base + "/admin/activity");
  await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
  check(true, label + " redirected home");
}

for (const base of ["", "/labadda-staging"]) {
  seed(base);
  const admin = await login(base, "admin");
  await checkAdministrator(admin, base);
  const reader = await login(base, "deepa");
  await checkReader(reader, base);
  const member = await login(base, "bharat");
  await checkMember(member, base);
  for (const session of [admin, reader, member]) await session.context.close();
}
await browser.close();
console.log(`console-activity: ${checks} checks passed`);
