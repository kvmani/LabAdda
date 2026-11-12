// A6 Overview at / and /labadda-staging: nothing-needs-attention, severity order, links, polling, readers.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-console-overview";
mkdirSync(output, { recursive: true });
const runDirectory = process.env.LABADDA_RUN_DIR ?? root + "var/proxy-stack";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
const ITEMS = [
  "application",
  "database",
  "file_storage",
  "connections",
  "jobs",
  "response_time",
  "sign_in",
  "backups",
  "server",
  "certificate",
];
// The sampler re-reads the force file and the page polls every 15 s, so a change shows within ~35 s.
const SETTLE = 45_000;
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
const instance = (base) => runDirectory + (base ? "/staging" : "/root");
function fixture(base, mode) {
  execFileSync(root + ".venv/bin/python", [root + "e2e/overview-fixture.py", mode], {
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
// Every item healthy except the ones named, so the page shows only what the scenario sets up.
function force(base, except = {}) {
  const lines = ITEMS.filter((item) => !(item in except && except[item] === null)).map(
    (item) => `${item}=${except[item] ?? "healthy"}`,
  );
  writeFileSync(instance(base) + "/assets/.test-health-force", lines.join("\n"));
}
function receipt(base, hoursAgo) {
  const finished = new Date(Date.now() - hoursAgo * 3600_000).toISOString().replace(/\.\d+Z$/, "Z");
  writeFileSync(
    instance(base) + "/status/backup-status.json",
    JSON.stringify({
      format: 1,
      finished_at: finished,
      result: "success",
      size_bytes: 4096,
      verification: "passed",
      destination: "nas-room",
      schema: "0029",
      release: "r1",
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

const TILES = [
  "People active today",
  "Signed in now",
  "Connected now",
  "Storage used",
  "Last backup",
  "Open events",
];

async function checkClean(page, base, tag) {
  const label = base + " clean";
  fixture(base, "clean");
  force(base);
  receipt(base, 2);
  await page.goto(origin + base + "/admin");
  await page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
  await page.getByText("Nothing needs attention", { exact: true }).first().waitFor({ timeout: SETTLE });
  check(true, label + " says plainly that nothing needs attention");
  const band = page.getByRole("region", { name: "Overall state" });
  check(
    (await band.getByText("Healthy", { exact: true }).count()) === 1,
    label + " overall state is healthy",
  );
  for (const name of TILES) {
    check(await page.getByRole("link", { name, exact: true }).isVisible(), `${label} tile ${name}`);
  }
  const tile = (name) => page.locator(".ui-stat-tile", { hasText: name }).innerText();
  check(/(KiB|MiB|GiB)/.test(await tile("Storage used")), label + " storage used is measured");
  check(/connections?/.test(await tile("Connected now")), label + " connected now is measured");
  check(
    !/Not measured/.test(await tile("Signed in now")),
    label + " signed in now is a figure or hidden below 5, never missing",
  );
  const backup = await page.locator(".ui-stat-tile", { hasText: "Last backup" }).innerText();
  check(/2 hours ago/.test(backup), label + " last backup age in words");
  check((await page.locator("svg.ui-sparkline").count()) >= 5, label + " tiles carry sparklines");
  check(
    (await page.getByRole("img", { name: /Slowest response time each day/ }).count()) +
      (await page.getByText("Slowest response time each day").count()) >
      0,
    label + " response-time chart is drawn from stored samples",
  );
  check(
    !(await page.locator(".ui-stat-tile").allInnerTexts()).some((text) => /(^|\n)0 people/.test(text)),
    label + " no hidden figure is shown as zero",
  );
  await page.screenshot({ path: `${output}/overview-clean-${tag}.png`, fullPage: true });
  for (const width of [1400, 390]) await audit(page, width, label);
}

async function checkProblems(page, base, tag) {
  const label = base + " problems";
  fixture(base, "problems");
  force(base, { backups: null });
  receipt(base, 60);
  await page.goto(origin + base + "/admin");
  const list = page.getByRole("list", { name: /Needs attention/ });
  await list.waitFor({ timeout: SETTLE });
  await page.getByText("3 things need attention.").waitFor({ timeout: SETTLE });
  const entries = await list.getByRole("listitem").allInnerTexts();
  check(entries.length === 3, label + " three entries");
  check(/Urgent/.test(entries[0]) && /scheduled task has not run/.test(entries[0]), label + " event first");
  check(/Unavailable/.test(entries[1]) && /Backups/.test(entries[1]), label + " stale backup second");
  check(
    /Warning/.test(entries[2]) && /Catalysis Section/.test(entries[2]),
    label + " unit without steward last",
  );
  await page.screenshot({ path: `${output}/overview-problems-${tag}.png`, fullPage: true });
  await page.getByRole("link", { name: "Open Backups", exact: true }).click();
  await page.waitForURL(/\/admin\/backups$/);
  check(true, label + " backup entry opens Backups");
  await page.goBack();
  await page.getByRole("link", { name: /^Open 1 unit has no steward/ }).click();
  await page.waitForURL(/\/admin\/org$/);
  check(true, label + " unit entry opens Organisation");
  await page.goBack();
  await page.getByRole("link", { name: /^Open A scheduled task has not run/ }).click();
  await page.waitForURL(/\/admin\/events\?state=open&event=\d+$/);
  check(true, label + " event entry opens the event");
  await page.goto(origin + base + "/admin");
  await page.getByRole("link", { name: "Open events", exact: true }).click();
  await page.waitForURL(/\/admin\/events\?state=open$/);
  check(true, label + " open-events tile opens the list");
  for (const width of [1400, 390]) {
    await page.goto(origin + base + "/admin");
    await page.getByText("3 things need attention.").waitFor();
    await audit(page, width, label);
  }
}

async function checkPolling(page, base) {
  const label = base + " polling";
  fixture(base, "clean");
  receipt(base, 2);
  force(base);
  await page.goto(origin + base + "/admin");
  await page.getByText("Nothing needs attention", { exact: true }).first().waitFor({ timeout: SETTLE });
  force(base, { database: "degraded" });
  await page.getByRole("link", { name: "Open Database", exact: true }).waitFor({ timeout: SETTLE });
  check(true, label + " a new problem appears without reloading");
  force(base);
  await page.getByText("Nothing needs attention", { exact: true }).first().waitFor({ timeout: SETTLE });
  check(true, label + " it leaves the list when fixed");
  check(
    await page
      .getByText(/^Updated \d+ s ago$/)
      .first()
      .isVisible(),
    label + " says when it was updated",
  );
}

async function checkReader(reader, base) {
  await reader.page.goto(origin + base + "/admin");
  await reader.page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
  await reader.page.getByRole("link", { name: "Storage used", exact: true }).waitFor({ timeout: SETTLE });
  check(true, base + " usage reader sees the overview");
}

async function checkMember(member, base) {
  const response = await member.context.request.get(origin + base + "/api/v1/admin/overview");
  check(response.status() === 403, base + " member refused");
  await member.page.goto(origin + base + "/admin");
  await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
  check(true, base + " member redirected home");
}

try {
  for (const [base, tag] of [
    ["", "root"],
    ["/labadda-staging", "prefix"],
  ]) {
    rmSync(instance(base) + "/status/backup-status.json", { force: true });
    const admin = await login(base, "admin");
    const reader = await login(base, "dana");
    const member = await login(base, "ben");
    try {
      await checkClean(admin.page, base, tag);
      await checkProblems(admin.page, base, tag);
      await checkPolling(admin.page, base);
      await checkReader(reader, base);
      await checkMember(member, base);
    } finally {
      for (const session of [admin, reader, member]) await session.context.close();
      rmSync(instance(base) + "/assets/.test-health-force", { force: true });
      rmSync(instance(base) + "/status/backup-status.json", { force: true });
      fixture(base, "restore");
    }
  }
  console.log(`console-overview: ${checks} checks passed`);
} finally {
  await browser.close();
}
