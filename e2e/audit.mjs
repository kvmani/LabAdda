// A2 audit explorer: filters in the URL, paging, drawer, audited export and denial at / and /labadda-staging.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-audit";
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
  execFileSync(root + ".venv/bin/python", [root + "e2e/audit-fixture.py"], {
    cwd: root,
    env: {
      ...process.env,
      PYTHONPATH: root + "backend",
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
    timezoneId: "America/Los_Angeles",
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
}
async function browse(page, base) {
  await page.goto(origin + base + "/admin/audit");
  await page.getByRole("table", { name: "Audit trail, newest first" }).waitFor();
  await page.getByRole("button", { name: "Older entries", exact: true }).click();
  await page.getByRole("button", { name: "Newest entries", exact: true }).waitFor();
  check(new URL(page.url()).searchParams.has("cursor"), base + " audit pages by URL cursor");
  await page.getByRole("button", { name: "Newest entries", exact: true }).click();
  await page.getByRole("button", { name: "Older entries", exact: true }).waitFor();
}
async function filters(page, base) {
  await page.getByRole("searchbox", { name: "Search reasons" }).fill("browser check 01");
  await page.getByText("Showing 10 entries on this page.").waitFor();
  check(
    await page.getByRole("searchbox").evaluate((input) => input === document.activeElement),
    base + " debounced search keeps focus",
  );
  await page.getByLabel("Kind of change", { exact: true }).selectOption("access");
  await page.getByText("No audit entries match these filters", { exact: true }).waitFor();
  check(true, base + " combined filters give a useful empty state");
  await page.getByRole("button", { name: "Clear audit filters" }).first().click();
  await page.getByLabel("Outcome", { exact: true }).selectOption("denied");
  await page
    .getByRole("button", { name: /^Open details: .* signed in\.$/ })
    .first()
    .waitFor();
  await page.getByLabel("From date", { exact: true }).fill("2030-01-01");
  await page.getByText("No audit entries match these filters", { exact: true }).waitFor();
  await page.getByLabel("From date", { exact: true }).fill("2026-01-06");
  await page.getByLabel("To date", { exact: true }).fill("2026-01-06");
  await page
    .getByRole("button", { name: /^Open details: .* signed in\.$/ })
    .first()
    .waitFor();
  await page.reload();
  await page
    .getByRole("button", { name: /^Open details: .* signed in\.$/ })
    .first()
    .waitFor();
  check(
    (await page.getByLabel("Outcome", { exact: true }).inputValue()) === "denied" &&
      (await page.getByLabel("To date", { exact: true }).inputValue()) === "2026-01-06",
    base + " refresh keeps every filter",
  );
  await page.getByRole("button", { name: "Clear audit filters" }).first().click();
  await page.getByLabel("Done by", { exact: true }).selectOption({ label: "Bharat Kulkarni (bharat)" });
  await page
    .getByRole("button", { name: /^Open details: .* signed in\.$/ })
    .first()
    .waitFor();
  check(true, base + " person filter applies");
  await page.getByRole("button", { name: "Clear audit filters" }).first().click();
}
async function detail(page, base) {
  await page.getByLabel("Kind of change", { exact: true }).selectOption("access");
  const opener = page.getByRole("button", { name: /^Open details: .* set the role of/ });
  await opener.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Audit entry", exact: true });
  await dialog.getByRole("heading", { name: "Before and after" }).waitFor();
  const text = await dialog.innerText();
  check(text.includes("Role review") && text.includes("steward"), base + " drawer shows sentence and reason");
  check(
    (await dialog.getByRole("cell", { name: "member", exact: true }).count()) === 1,
    base + " drawer shows before and after values",
  );
  await page.reload();
  await page.getByRole("dialog", { name: "Audit entry" }).waitFor();
  check(new URL(page.url()).searchParams.has("entry"), base + " entry deep link survives refresh");
  await audit(page, 1400, base + " audit drawer");
  await audit(page, 390, base + " audit drawer");
  await page.setViewportSize({ width: 1400, height: 1100 });
  await page.screenshot({
    path: output + (base ? "/prefix-drawer.png" : "/root-drawer.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await opener.click();
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  check(
    await opener.evaluate((button) => button === document.activeElement),
    base + " closing returns focus to the entry",
  );
  await page.getByRole("button", { name: "Clear audit filters" }).first().click();
  await page.getByRole("button", { name: "Older entries", exact: true }).waitFor();
  await audit(page, 1400, base + " audit list");
  await audit(page, 390, base + " audit list");
  await page.setViewportSize({ width: 1400, height: 1100 });
  await page.screenshot({ path: output + (base ? "/prefix-list.png" : "/root-list.png"), fullPage: true });
}
async function report(page, base) {
  await page.getByRole("searchbox", { name: "Search reasons" }).fill("HYPERLINK");
  await page.getByText("Showing 1 entry on this page.").waitFor();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export matching entries", exact: true }).click();
  const file = await download;
  const csv = readFileSync(await file.path(), "utf8");
  check(csv.includes("'=HYPERLINK(1)") && !csv.includes("Role review"), base + " CSV honours filters");
  check(!/(^|,)"?=/m.test(csv), base + " CSV has no formula cell");
  await page.getByText("Report prepared.").waitFor();
  await page.getByRole("button", { name: "Clear audit filters" }).first().click();
  await page.getByLabel("Kind of change", { exact: true }).selectOption("exports");
  await page.getByRole("button", { name: /exported 1 entries of the audit trail/ }).waitFor();
  check(true, base + " the export is itself in the audit trail");
}
async function offline(page, base) {
  await page.goto(origin + base + "/admin/audit");
  await page.getByRole("table", { name: "Audit trail, newest first" }).waitFor();
  await page.route("**/api/v1/admin/audit?**", (route) => route.abort(), { times: 1 });
  await page.getByLabel("Outcome", { exact: true }).selectOption("failed");
  await page.getByRole("button", { name: "Try again" }).waitFor();
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByText("No audit entries match these filters", { exact: true }).waitFor();
  check(true, base + " a failed load offers retry and recovers");
}
try {
  for (const base of ["", "/labadda-staging"]) {
    seed(base);
    const admin = await login(base, "admin");
    const member = await login(base, "bharat");
    try {
      await browse(admin.page, base);
      await filters(admin.page, base);
      await detail(admin.page, base);
      await report(admin.page, base);
      await offline(admin.page, base);
      await member.page.goto(origin + base + "/admin/audit");
      await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
      const api = origin + base + "/api/v1/admin/audit";
      check(
        (await member.context.request.get(api)).status() === 403,
        base + " member cannot read the audit trail",
      );
      check(
        (await member.context.request.get(api + "/export.csv")).status() === 403,
        base + " member cannot export the audit trail",
      );
      check((await fetch(api)).status === 401, base + " signed-out request is refused");
    } finally {
      await Promise.all([admin.context.close(), member.context.close()]);
    }
  }
  console.log(`${checks} audit browser checks passed`);
} finally {
  await browser.close();
}
