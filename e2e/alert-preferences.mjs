import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const browser = await chromium.launch({
    executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
  }),
  origin = "http://127.0.0.1:8080",
  out = process.argv[2] ?? "/tmp/c5-preferences";
mkdirSync(out, { recursive: true });
let checks = 0;
const check = (value, label) => {
  assert.ok(value, label);
  checks++;
  console.log("PASS " + label);
};
async function login(base, name) {
  const ctx = await browser.newContext({
      viewport: { width: 1400, height: 1100 },
      timezoneId: "Asia/Kolkata",
    }),
    page = await ctx.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Sign out" }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return {
    ctx,
    page,
    errors,
    session,
    api: origin + base + "/api/v1",
    headers: { "X-CSRF-Token": session.csrf_token },
  };
}
async function call(a, path, body, method = body ? "POST" : "GET") {
  const response = await a.ctx.request.fetch(a.api + path, { method, headers: a.headers, data: body });
  assert.ok(response.ok(), await response.text());
  return response.json();
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const ben = await login(base, "ben"),
      asha = await login(base, "asha"),
      chen = await login(base, "chen");
    const ws = (await call(ben, "/workspaces")).workspaces.find(
      (row) => row.name === "Thin Films Section",
    ).id;
    const mention = (text) =>
      call(asha, `/workspaces/${ws}/chat`, { body: "@ben " + text, client_id: crypto.randomUUID() });
    await mention("Before muting");
    await ben.page.goto(origin + base + "/preferences");
    await ben.page.getByText("Current alert choices loaded.", { exact: true }).waitFor();
    check(
      await ben.page.getByLabel("Mentions in posts and chat", { exact: true }).isChecked(),
      base + " compatible alert defaults are enabled",
    );
    await ben.page.getByLabel("Mentions in posts and chat", { exact: true }).uncheck();
    await ben.page.getByLabel("Scheduled note and post reminders", { exact: true }).uncheck();
    await ben.page.route(
      "**/api/v1/notification-preferences",
      async (route) => {
        if (route.request().method() !== "PUT") return route.continue();
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await ben.page.getByRole("button", { name: "Save alert preferences", exact: true }).click();
    await ben.page
      .getByRole("button", { name: "Reload current preferences (replaces draft)", exact: true })
      .waitFor();
    check(
      await ben.page.getByRole("button", { name: "Save alert preferences", exact: true }).isDisabled(),
      base + " uncertain preference save blocks blind repeat",
    );
    await ben.page
      .getByRole("button", { name: "Reload current preferences (replaces draft)", exact: true })
      .click();
    await ben.page.getByRole("button", { name: "Refresh alert preferences", exact: true }).waitFor();
    check(
      !(await ben.page.getByLabel("Mentions in posts and chat", { exact: true }).isChecked()),
      base + " explicit reload recovers committed alert choices",
    );
    await mention("While muted");
    check(
      (await call(ben, "/notifications")).items.length === 1,
      base + " muted category creates no new alert and retains prior history",
    );
    await chen.page.goto(origin + base + "/preferences");
    await chen.page.getByText("Current alert choices loaded.", { exact: true }).waitFor();
    check(
      await chen.page.getByLabel("Mentions in posts and chat", { exact: true }).isChecked(),
      base + " colleague preferences remain independent",
    );
    await ben.page.screenshot({
      path: out + "/" + (base ? "prefix" : "root") + "-alert-preferences.png",
      fullPage: true,
    });
    const second = await ben.ctx.newPage();
    await second.goto(origin + base + "/preferences");
    await second.getByText("Current alert choices loaded.", { exact: true }).waitFor();
    await second.getByLabel("Official notice alerts", { exact: true }).uncheck();
    await ben.page.getByLabel("Mentions in posts and chat", { exact: true }).check();
    await ben.page.getByLabel("Scheduled note and post reminders", { exact: true }).check();
    await ben.page.getByRole("button", { name: "Save alert preferences", exact: true }).click();
    await ben.page.getByText("Alert preferences saved.", { exact: true }).waitFor();
    await second.getByRole("button", { name: "Save alert preferences", exact: true }).click();
    await second
      .getByRole("button", { name: "Reload current preferences (replaces draft)", exact: true })
      .waitFor();
    check(
      !(await second.getByLabel("Official notice alerts", { exact: true }).isChecked()),
      base + " concurrent settings conflict retains draft instead of overwriting",
    );
    await second
      .getByRole("button", { name: "Reload current preferences (replaces draft)", exact: true })
      .click();
    await second.getByRole("button", { name: "Refresh alert preferences", exact: true }).waitFor();
    check(
      await second.getByLabel("Official notice alerts", { exact: true }).isChecked(),
      base + " explicit conflict reload shows latest owner choices",
    );
    await second.close();
    await mention("After enabling");
    check(
      (await call(ben, "/notifications")).items.length === 2,
      base + " enabling resumes new alerts without replaying skipped occurrence",
    );
    for (const width of [1400, 390]) {
      await ben.page.setViewportSize({ width, height: 1100 });
      await ben.page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
      const violations = await ben.page.evaluate(async () =>
        (
          await window.axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
          })
        ).violations.map((v) => v.id),
      );
      check(!violations.length, base + " preferences accessibility " + width + " " + violations);
      check(
        await ben.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        base + " preferences overflow " + width,
      );
    }
    await ben.page.getByLabel("Switch workspace", { exact: true }).selectOption("today");
    await ben.page.getByRole("heading", { name: "My day", exact: true }).waitFor();
    check(
      (await ben.page.getByLabel("Switch workspace", { exact: true }).inputValue()) === "today",
      base + " mobile menu selects daily overview",
    );
    await ben.page.getByLabel("Switch workspace", { exact: true }).selectOption("private_conversation");
    await ben.page.getByRole("heading", { name: "Start a private conversation", exact: true }).waitFor();
    check(
      (await ben.page.getByLabel("Switch workspace", { exact: true }).inputValue()) ===
        "private_conversation",
      base + " mobile menu exposes private conversation creation",
    );
    const today = (await call(ben, "/dashboard")).today;
    const personal = await call(ben, "/todos/lists", {
      title: "Daily calibration notes",
      client_id: crypto.randomUUID(),
    });
    await call(ben, `/todos/lists/${personal.id}/tasks`, {
      title: "Inspect 40 nm reference drift",
      due_date: today,
      priority: "high",
      client_id: crypto.randomUUID(),
    });
    const shared = await call(asha, "/todos/lists", {
        title: "Cross-check controls",
        workspace_id: ws,
        client_id: crypto.randomUUID(),
      }),
      work = await call(asha, `/todos/lists/${shared.id}/tasks`, {
        title: "Resolve catalyst control uncertainty",
        due_date: today,
        client_id: crypto.randomUUID(),
      });
    await call(
      asha,
      `/todos/lists/${shared.id}/tasks/${work.id}/assignee`,
      { revision: 1, user_id: ben.session.user.id },
      "PUT",
    );
    await call(ben, "/notes", {
      title: "Before division review",
      body: "Compare blank and witness uncertainty before sharing the conclusion.",
      due_at: new Date(Date.now() + 86400000).toISOString(),
    });
    await ben.page.setViewportSize({ width: 1400, height: 1100 });
    await ben.page.goto(origin + base + "/today");
    await ben.page.getByRole("link", { name: "Inspect 40 nm reference drift", exact: true }).waitFor();
    await ben.page.screenshot({
      path: out + "/" + (base ? "prefix" : "root") + "-my-day.png",
      fullPage: true,
    });
    check(!ben.errors.length && !chen.errors.length, base + " no browser exceptions");
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close()]);
  }
  console.log(`${checks} alert preference browser checks passed`);
} finally {
  await browser.close();
}
