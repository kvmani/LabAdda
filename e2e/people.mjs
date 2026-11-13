// P1 staff metadata, URL navigation, downloads and delivery races through root/prefix proxies.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-people";
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
  execFileSync(root + ".venv/bin/python", [root + "e2e/people-fixture.py"], {
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
async function filter(page, value, name) {
  await page.getByRole("searchbox", { name: "Search people" }).fill(value);
  await page.getByRole("button", { name: `View profile for ${name}`, exact: true }).waitFor();
}
async function directory(page, base) {
  await page.goto(origin + base + "/admin/people");
  await page.getByRole("button", { name: "Next people page", exact: true }).click();
  await page.getByRole("button", { name: "First people page", exact: true }).waitFor();
  check(new URL(page.url()).searchParams.has("cursor"), base + " directory pages by URL cursor");
  await page.getByRole("button", { name: "First people page", exact: true }).click();
  await filter(page, "NM-100", "Bharat Kulkarni");
  check(!new URL(page.url()).searchParams.has("cursor"), base + " new search resets pagination");
  check(
    await page.getByRole("searchbox").evaluate((input) => input === document.activeElement),
    base + " debounced search preserves focus",
  );
  await page.getByLabel("Employment status", { exact: true }).selectOption("left");
  await page.getByText("No people match these filters", { exact: true }).waitFor();
  check(true, base + " status filter has useful empty state");
  await page.getByLabel("Employment status", { exact: true }).selectOption("active");
  await page.getByRole("button", { name: "View profile for Bharat Kulkarni", exact: true }).waitFor();
  await page.getByLabel("Sort people by").selectOption("employee_no");
  await page.getByLabel("Descending order", { exact: true }).check();
  await page.reload();
  await page.getByRole("button", { name: "View profile for Bharat Kulkarni", exact: true }).waitFor();
  check(
    await page.getByLabel("Descending order", { exact: true }).isChecked(),
    base + " refresh preserves filters and order",
  );
  await audit(page, 1400, base + " directory");
  await audit(page, 390, base + " directory");
  await page.screenshot({
    path: output + (base ? "/prefix-directory.png" : "/root-directory.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1400, height: 1100 });
}
async function profile(page, base) {
  const opener = page.getByRole("button", { name: "View profile for Bharat Kulkarni", exact: true });
  await opener.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Bharat Kulkarni", exact: true });
  await dialog.getByText("bharat@research.example", { exact: true }).waitFor();
  check(
    await dialog.getByText("3 Jul 2023", { exact: true }).isVisible(),
    base + " date stays in site calendar",
  );
  await dialog.getByRole("tab", { name: "Access", exact: true }).click();
  await dialog.getByText("Thin Films Section", { exact: true }).waitFor();
  check(
    (await dialog.getByText("Inherited from a child unit", { exact: true }).count()) === 3,
    base + " profile describes upward inheritance",
  );
  await dialog.getByRole("tab", { name: "Timeline", exact: true }).focus();
  await page.keyboard.press("Enter");
  await dialog.getByText("Synthetic staff review", { exact: true }).waitFor();
  check(
    !(await dialog.innerText()).includes("PRIVATE-AUDIT-DETAIL"),
    base + " timeline excludes raw audit detail",
  );
  await page.reload();
  await page.getByRole("dialog").getByText("Synthetic staff review", { exact: true }).waitFor();
  check(new URL(page.url()).searchParams.get("view") === "timeline", base + " profile deep link refreshes");
  await audit(page, 1400, base + " profile");
  await audit(page, 390, base + " profile");
  await page.screenshot({
    path: output + (base ? "/prefix-profile.png" : "/root-profile.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await opener.waitFor();
  await opener.click();
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  check(
    await opener.evaluate((button) => button === document.activeElement),
    base + " closing returns focus to selected person",
  );
  check(new URL(page.url()).searchParams.get("q") === "NM-100", base + " profile preserves list filters");
}
async function report(page, base) {
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export matching people", exact: true }).click();
  const file = await download;
  const csv = readFileSync(await file.path(), "utf8");
  check(csv.includes("NM-100") && !csv.includes("Chitra Iyer"), base + " CSV uses all matching filters");
  check(
    !csv.includes("bharat@research.example") &&
      !csv.includes("contact_email") &&
      !csv.includes("PRIVATE-AUDIT-DETAIL"),
    base + " CSV excludes contacts and private detail",
  );
}
async function hold(page, pattern) {
  let entered;
  let release;
  let finished;
  // A request that never arrives must fail the suite, not stall the whole browser run.
  const waiting = new Promise((resolve, reject) => {
    entered = resolve;
    setTimeout(() => reject(new Error("held request never arrived: " + pattern)), 30_000);
  });
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const completion = new Promise((resolve) => {
    finished = resolve;
  });
  await page.route(
    pattern,
    async (route) => {
      const response = await route.fetch();
      entered();
      await gate;
      await route.fulfill({ response });
      finished();
    },
    { times: 1 },
  );
  return { waiting, release, completion };
}
async function races(admin, reviewer, base) {
  const { page } = admin;
  await page.goto(origin + base + "/admin/people?q=Chitra");
  await page.getByRole("button", { name: "View profile for Chitra Iyer", exact: true }).waitFor();
  const delayed = await hold(page, "**/api/v1/admin/people?q=Bharat");
  await page.getByRole("searchbox").fill("Bharat");
  await delayed.waiting;
  await filter(page, "Chitra", "Chitra Iyer");
  delayed.release();
  await delayed.completion;
  check(
    (await page.getByRole("button", { name: "View profile for Bharat Kulkarni", exact: true }).count()) === 0,
    base + " late directory response cannot replace current filter",
  );
  const pending = await hold(page, "**/api/v1/admin/people?q=Bharat");
  await page.getByRole("searchbox").fill("Bharat");
  await pending.waiting;
  const endpoint = origin + base + "/api/v1";
  const session = await (await reviewer.context.request.get(endpoint + "/auth/session")).json();
  const users = await (await reviewer.context.request.get(endpoint + "/admin/users")).json();
  const original = users.users.find((person) => person.username === "admin");
  const patch = (is_admin) =>
    reviewer.context.request.patch(endpoint + "/admin/users/" + original.id, {
      headers: { "X-CSRF-Token": session.csrf_token },
      data: { is_admin },
    });
  check((await patch(false)).ok(), base + " authority revocation committed");
  try {
    await page.getByRole("button", { name: "Refresh directory", exact: true }).click();
    await page.getByText("Your administration access changed", { exact: true }).waitFor();
    pending.release();
    await pending.completion;
    check(
      (await page.getByRole("table", { name: "Staff directory", exact: true }).count()) === 0,
      base + " revoked authority clears data and rejects held success",
    );
  } finally {
    pending.release();
    check((await patch(true)).ok(), base + " synthetic administrator restored");
  }
}
try {
  for (const base of ["", "/labadda-staging"]) {
    seed(base);
    const admin = await login(base, "admin");
    const reviewer = await login(base, "reviewadmin");
    const member = await login(base, "bharat");
    try {
      await directory(admin.page, base);
      await profile(admin.page, base);
      await report(admin.page, base);
      await member.page.goto(origin + base + "/admin/people");
      await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
      check(
        (await member.context.request.get(origin + base + "/api/v1/admin/people")).status() === 403,
        base + " member has no staff-directory access",
      );
      await races(admin, reviewer, base);
    } finally {
      await Promise.all([admin.context.close(), reviewer.context.close(), member.context.close()]);
    }
  }
  console.log(`${checks} people browser checks passed`);
} finally {
  await browser.close();
}
