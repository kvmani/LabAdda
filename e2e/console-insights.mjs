// Insights page at / and /labadda-staging: feature trends, performance, access and layout.
// LABADDA_E2E_ORIGIN and LABADDA_E2E_BASES (comma-separated, "" for root) point it elsewhere.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8080";
const bases = (process.env.LABADDA_E2E_BASES ?? ",/labadda-staging").split(",");
const output = process.argv[2] ?? "/tmp/labadda-console-insights";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch(
  process.env.LABADDA_CHROMIUM === ""
    ? {}
    : { executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium" },
);
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
function seed(base) {
  if (process.env.LABADDA_E2E_SKIP_SEED) return;
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
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { context, page, errors };
}
async function fits(page, width, label) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(300);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}`,
  );
  await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((item) => item.id),
  );
  check(violations.length === 0, `${label} accessibility ${width}: ${violations}`);
  await page.setViewportSize({ width: 1400, height: 1100 });
}

async function checkAdministrator(base) {
  const admin = await login(base, "admin");
  const { page } = admin;
  const label = base + " insights";
  const navigation = page.getByRole("navigation", { name: "Administration", exact: true });
  await page.goto(origin + base + "/admin");
  await navigation.getByRole("link", { name: "Insights", exact: true }).click();
  await page.getByRole("heading", { name: "Insights", exact: true }).waitFor();
  check(
    (await page.getByRole("tab", { name: "Feature trends" }).getAttribute("aria-selected")) === "true",
    label + " opens on feature trends",
  );
  await page
    .getByText(/What to do next|Not measured yet|Hidden to protect privacy/)
    .first()
    .waitFor();
  check(true, label + " trends show a designed state");
  check(
    (await page.getByLabel("Period", { exact: true }).inputValue()) === "12",
    label + " defaults to 12 weeks",
  );
  await page.getByLabel("Period", { exact: true }).selectOption("26");
  await page.waitForURL(/weeks=26/);
  check(true, label + " trend period kept in the address");
  await fits(page, 390, label + " trends");
  await page.screenshot({ path: output + (base ? "/prefix" : "/root") + "-trends.png", fullPage: true });

  await page.getByRole("tab", { name: "Performance" }).click();
  await page.waitForURL(/view=performance/);
  await page
    .getByText(/Slowest 5 % of requests|Not measured yet/)
    .first()
    .waitFor();
  check(true, label + " performance shows a designed state");
  await page.getByLabel("Period", { exact: true }).selectOption("24h");
  await page.waitForURL(/span=24h/);
  await page.reload();
  await page.getByRole("heading", { name: "Insights", exact: true }).waitFor();
  check(
    (await page.getByRole("tab", { name: "Performance" }).getAttribute("aria-selected")) === "true",
    label + " deep link survives refresh",
  );
  await fits(page, 390, label + " performance");
  await page.screenshot({ path: output + (base ? "/prefix" : "/root") + "-performance.png", fullPage: true });
  check(admin.errors.length === 0, label + " no script errors: " + admin.errors.join("; "));
  await admin.context.close();
}

async function checkMember(base) {
  const member = await login(base, "asha");
  const endpoint = origin + base + "/api/v1/admin/insights";
  for (const path of ["/trends", "/performance"]) {
    check(
      (await member.context.request.get(endpoint + path)).status() === 403,
      `${base} member denied ${path}`,
    );
  }
  await member.context.close();
}

for (const base of bases) {
  seed(base);
  await checkAdministrator(base);
  await checkMember(base);
}
await browser.close();
console.log(`console-insights: ${checks} checks passed`);
