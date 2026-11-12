// A1 current-authority navigation, honest placeholders and preserved basic tools.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-admin-console";
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
async function audit(page, width, base) {
  await page.setViewportSize({ width, height: 1100 });
  await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((violation) => violation.id),
  );
  check(violations.length === 0, base + " console accessibility " + width + " " + violations);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    base + " console page fits " + width,
  );
}
async function checkChunkRecovery(admin, base) {
  const chunk = /\/assets\/Admin-[^/]+\.js$/;
  const unavailable = (route) => route.abort();
  // Vite can request a module once for preload and again for import; fail both.
  await admin.page.route(chunk, unavailable);
  await admin.page.goto(origin + base + "/admin");
  await admin.page.getByRole("alert").filter({ hasText: "Administration could not be loaded" }).waitFor();
  check(
    await admin.page.getByRole("link", { name: "LabAdda", exact: true }).isVisible(),
    base + " failed console chunk leaves application navigation available",
  );
  await admin.page.unroute(chunk, unavailable);
  await admin.page.getByRole("button", { name: "Reload administration", exact: true }).click();
  await admin.page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
  check(true, base + " console chunk failure recovers through explicit reload");
}

async function checkAdmin(admin, base) {
  const { page } = admin;
  await page.goto(origin + base + "/admin");
  await page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
  await page.getByRole("region", { name: "Overall state" }).waitFor();
  check(true, base + " overview page is the console index");
  const navigation = page.getByRole("navigation", { name: "Administration", exact: true });
  check((await navigation.getByRole("link").count()) === 11, base + " eleven administrator sections");
  await navigation.getByRole("link", { name: "People", exact: true }).click();
  await page.getByRole("link", { name: "Basic account tools", exact: true }).click();
  await page.getByRole("heading", { name: "Accounts", exact: true }).waitFor();
  check(await page.getByLabel("Username", { exact: true }).isVisible(), base + " basic accounts preserved");
  check(
    (await page.getByRole("heading", { name: "Workspaces", exact: true }).count()) === 0,
    base + " organisation tools have their own page",
  );
  await page.reload();
  await page.getByRole("heading", { name: "People (basic)", exact: true }).waitFor();
  check(true, base + " deep link survives refresh");
  await navigation.getByRole("link", { name: "Organisation", exact: true }).click();
  await page.getByRole("link", { name: "Basic project tools", exact: true }).click();
  await page.getByRole("heading", { name: "Workspaces", exact: true }).waitFor();
  check(
    await page.getByLabel("Workspace name", { exact: true }).isVisible(),
    base + " basic units preserved",
  );
  await page.getByRole("button", { name: "Thin Films Section", exact: true }).click();
  await page.getByRole("heading", { name: "Memberships · Thin Films Section", exact: true }).waitFor();
  check(await page.getByLabel("User", { exact: true }).isVisible(), base + " membership tools preserved");
  await navigation.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Operational reader account").waitFor();
  check(
    (await page.getByRole("heading", { name: "Workspaces", exact: true }).count()) === 0,
    base + " settings contains delegation tools only",
  );
  await audit(page, 1400, base);
  await audit(page, 390, base);
  await page.getByLabel("Administration section", { exact: true }).selectOption("/admin/health");
  await page.getByRole("heading", { name: "System health", exact: true }).waitFor();
  check(
    await page.getByRole("heading", { name: "System health", exact: true }).isVisible(),
    base + " mobile navigation",
  );
  await page.screenshot({
    path: output + (base ? "/prefix-console.png" : "/root-console.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1400, height: 1100 });
}
async function checkAuthorityRace(admin, base) {
  const { page } = admin;
  let release;
  let entered;
  let completed;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const waiting = new Promise((resolve) => {
    entered = resolve;
  });
  const finished = new Promise((resolve) => {
    completed = resolve;
  });
  await page.route(
    "**/api/v1/admin/console",
    async (route) => {
      const response = await route.fetch();
      entered();
      await gate;
      await route.fulfill({ response });
      completed();
    },
    { times: 1 },
  );
  await page
    .getByRole("navigation", { name: "Administration", exact: true })
    .getByRole("link", { name: "Overview", exact: true })
    .click();
  await waiting;
  await page.goBack();
  await page.getByRole("heading", { name: "System health", exact: true }).waitFor();
  release();
  await finished;
  check(
    await page.getByRole("heading", { name: "System health", exact: true }).isVisible(),
    base + " late navigation authority cannot replace the current page",
  );
}

async function checkLookupRecovery(admin, base) {
  const { page } = admin;
  // Failure/retry is independent of the preceding history-navigation race.
  await page.goto(origin + base + "/admin/health");
  await page.getByRole("heading", { name: "System health", exact: true }).waitFor();
  // Keep the lookup unavailable until the explicit retry; queued navigation lookups
  // must not consume a one-response fault and turn this into a timing-dependent check.
  const unavailable = (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "synthetic_unavailable", message: "Synthetic lookup unavailable." },
      }),
    });
  await page.route("**/api/v1/admin/console", unavailable);
  const failedLookup = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/admin/console") && response.status() === 503,
  );
  await page
    .getByRole("navigation", { name: "Administration", exact: true })
    .getByRole("link", { name: "Overview", exact: true })
    .click();
  await failedLookup;
  await page.getByRole("alert").filter({ hasText: "Synthetic lookup unavailable." }).waitFor();
  check(new URL(page.url()).pathname === base + "/admin", base + " failed lookup belongs to current section");
  await page.unroute("**/api/v1/admin/console", unavailable);
  const successfulLookup = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/admin/console") && response.status() === 200,
  );
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await successfulLookup;
  await page.getByRole("heading", { name: "Overview", exact: true }).waitFor();
  check(true, base + " failed authority lookup retries without stale content");
}

async function checkReader(admin, member, base) {
  const endpoint = origin + base + "/api/v1";
  const session = await (await admin.context.request.get(endpoint + "/auth/session")).json();
  const users = await (await admin.context.request.get(endpoint + "/admin/users")).json();
  const user = users.users.find((person) => person.username === "ben");
  const response = await admin.context.request.post(endpoint + "/admin/usage-readers", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: {
      user_id: user.id,
      hours: 1,
      reason: "Synthetic console walkthrough",
      password: "fixture-pass-123",
    },
  });
  check(response.ok(), base + " grant remains explicit");
  await member.page.goto(origin + base + "/operations");
  await member.page.getByRole("heading", { name: "Partial site measurement", exact: true }).waitFor();
  check(member.page.url().endsWith(base + "/admin/storage"), base + " legacy operations link redirects");
  const navigation = member.page.getByRole("navigation", { name: "Administration", exact: true });
  check((await navigation.getByRole("link").count()) === 6, base + " six read-only sections");
  check(
    (await navigation.getByRole("link", { name: "People", exact: true }).count()) === 0,
    base + " identity management hidden from reader",
  );
  await member.page.goto(origin + base + "/admin/settings");
  await member.page.getByRole("alert").filter({ hasText: "needs administrator access" }).waitFor();
  check(
    (await member.context.request.get(endpoint + "/admin/usage-readers")).status() === 403,
    base + " reader denied through direct API",
  );
  const revoked = await admin.context.request.post(endpoint + "/admin/usage-readers/revoke", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: { user_id: user.id, reason: "Synthetic access review finished", password: "fixture-pass-123" },
  });
  check(revoked.ok(), base + " revocation committed");
  await member.page.goto(origin + base + "/admin/activity");
  await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
  check(
    (await member.context.request.get(endpoint + "/admin/console")).status() === 403,
    base + " revoked reader redirected and API denied",
  );
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    const member = await login(base, "ben");
    await member.page.goto(origin + base + "/admin/people");
    await member.page.waitForURL((url) => !url.pathname.includes("/admin"));
    check(true, base + " ordinary member redirected home");
    await checkChunkRecovery(admin, base);
    await checkAdmin(admin, base);
    await checkAuthorityRace(admin, base);
    await checkLookupRecovery(admin, base);
    await checkReader(admin, member, base);
    await Promise.all([admin.context.close(), member.context.close()]);
  }
  console.log(`${checks} admin console browser checks passed`);
} finally {
  await browser.close();
}
