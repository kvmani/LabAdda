// C2 content-free hints and explicit catch-up, on fresh disposable proxy fixtures.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
const output = process.argv[2] ? resolve(process.argv[2]) : null;
if (output) mkdirSync(output, { recursive: true });
const { chromium } = createRequire(import.meta.url)("playwright");
const origin = "http://127.0.0.1:8080";
async function until(predicate) {
  for (let i = 0; i < 250; i++) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw Error("Expected socket frame not observed");
}
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(value, label) {
  assert.ok(value, label);
  checks++;
  console.log("PASS " + label);
}
async function login(base, name) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }),
    page = await ctx.newPage(),
    frames = [],
    errors = [];
  await ctx.addInitScript(() => {
    const Native = window.WebSocket;
    window.__reviewSockets = [];
    window.WebSocket = class extends Native {
      constructor(...args) {
        super(...args);
        window.__reviewSockets.push(this);
      }
    };
  });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("websocket", (socket) =>
    socket.on("framereceived", (frame) => {
      try {
        frames.push(JSON.parse(String(frame.payload)));
      } catch {}
    }),
  );
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return {
    ctx,
    page,
    session,
    frames,
    errors,
    api: origin + base + "/api/v1",
    headers: { "X-CSRF-Token": session.csrf_token },
  };
}
async function call(user, path, data, method = data ? "POST" : "GET") {
  const response = await user.ctx.request.fetch(user.api + path, { method, headers: user.headers, data });
  assert.ok(response.ok(), await response.text());
  return response.json();
}
const fields = (task) =>
  Object.fromEntries(
    ["title", "description", "due_date", "priority", "checklist", "done", "status", "revision"].map((key) => [
      key,
      task[key],
    ]),
  );
async function open(user, base, workspace, list) {
  await user.page.goto(origin + base + `/w/${workspace}/todos`);
  await user.page.getByRole("button", { name: list.title, exact: true }).click();
  await user.page.getByRole("heading", { name: "Plan experiment", exact: true }).waitFor();
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const ben = await login(base, "ben"),
      asha = await login(base, "asha"),
      chen = await login(base, "chen"),
      admin = await login(base, "admin");
    const spaces = (await call(ben, "/workspaces")).workspaces,
      section = spaces.find((w) => w.name === "Thin Films Section");
    const list = await call(asha, "/todos/lists", {
      client_id: crypto.randomUUID(),
      title: "Live project actions",
      workspace_id: section.id,
    });
    const path = `/todos/lists/${list.id}/tasks`;
    let task = await call(asha, path, { client_id: crypto.randomUUID(), title: "Plan experiment" }),
      detail = path + "/" + task.id;
    await open(ben, base, section.id, list);
    const shared = ben.page.getByRole("button", { name: "Check shared updates", exact: true });
    await shared.waitFor();
    await shared.click();
    await shared.waitFor({ state: "hidden" });
    await ben.page.getByRole("button", { name: "View comments", exact: true }).click();
    const discussion = ben.page.getByRole("region", { name: "Task comments", exact: true });
    await discussion.getByText("No comments yet.", { exact: true }).waitFor();
    await discussion.getByLabel("New task comment", { exact: true }).fill("Unsent uncertainty question");
    await ben.page.getByRole("button", { name: "Edit task: Plan experiment", exact: true }).click();
    await ben.page.getByLabel("Task title", { exact: true }).fill("Unsent editor draft");
    const assignment = ben.page.getByRole("region", { name: "Task assignment", exact: true });
    await assignment.getByRole("button", { name: "Change assignee", exact: true }).click();
    await assignment.getByLabel("Assignee", { exact: true }).selectOption(ben.session.user.id);
    task = await call(asha, detail, { ...fields(task), title: "Reviewed experiment" }, "PUT");
    await shared.waitFor();
    check(
      (await ben.page.getByLabel("Task title", { exact: true }).inputValue()) === "Unsent editor draft",
      base + " hint does not replace task draft",
    );
    await shared.click();
    await ben.page.getByRole("heading", { name: "Reviewed experiment", exact: true }).waitFor();
    check(
      (await discussion.getByLabel("New task comment", { exact: true }).inputValue()) ===
        "Unsent uncertainty question",
      base + " visible-card refresh preserves discussion draft",
    );
    check(
      (await assignment.getByLabel("Assignee", { exact: true }).inputValue()) === ben.session.user.id &&
        (await assignment.getByRole("button", { name: "Save assignment", exact: true }).isDisabled()),
      base + " changed revision preserves choice and requires assignment review",
    );
    if (output && base === "")
      await ben.page.screenshot({ path: output + "/shared-task-drafts.png", fullPage: true });
    await assignment.getByRole("button", { name: "Reload task assignment", exact: true }).click();
    await assignment.getByRole("button", { name: "Change assignee", exact: true }).waitFor();
    check(
      (await ben.page.getByLabel("Task title", { exact: true }).inputValue()) === "Unsent editor draft",
      base + " refresh keeps task editor draft and original write revision",
    );
    await ben.page.getByRole("button", { name: "Save task", exact: true }).click();
    await ben.page
      .getByText("This task changed. Refresh and review before saving again.", { exact: true })
      .waitFor();
    check(
      (await ben.page.getByLabel("Task title", { exact: true }).inputValue()) === "Unsent editor draft",
      base + " stale editor cannot overwrite the reviewed remote revision",
    );
    await ben.page.getByRole("button", { name: "Close editor", exact: true }).click();
    await call(asha, detail + "/comments", {
      client_id: crypto.randomUUID(),
      body: "Controls agreed by colleague",
    });
    await discussion
      .getByText("Shared discussion may have changed. Refresh comments; your draft is kept.", { exact: true })
      .waitFor();
    await discussion.getByRole("button", { name: "Refresh comments", exact: true }).click();
    await discussion.getByText("Controls agreed by colleague", { exact: true }).waitFor();
    check(
      (await discussion.getByLabel("New task comment", { exact: true }).inputValue()) ===
        "Unsent uncertainty question",
      base + " discussion catch-up keeps typed text",
    );
    // A hint while the HTTP snapshot is in flight cannot be acknowledged by that older response.
    let release, captured;
    const hold = new Promise((resolve) => (release = resolve)),
      ready = new Promise((resolve) => (captured = resolve));
    await ben.page.route(
      "**/api/v1" + detail,
      async (route) => {
        const response = await route.fetch();
        captured();
        await hold;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    await shared.click();
    await ready;
    const beforeHint = ben.frames.filter((f) => f.type === "tasks.changed").length;
    task = await call(asha, detail, { ...fields(task), title: "Second reviewed experiment" }, "PUT");
    await until(() => ben.frames.filter((f) => f.type === "tasks.changed").length > beforeHint);
    release();
    await ben.page.waitForFunction(() =>
      [...document.querySelectorAll("button")].some(
        (b) => b.textContent === "Check shared updates" && !b.disabled,
      ),
    );
    await shared.waitFor();
    check(await shared.isVisible(), base + " in-flight newer signal stays pending");
    await shared.click();
    await ben.page.getByRole("heading", { name: "Second reviewed experiment", exact: true }).waitFor();
    await shared.waitFor({ state: "hidden" });
    // A failed authorized read leaves the hint pending and the draft available.
    await call(asha, detail + "/comments", { client_id: crypto.randomUUID(), body: "Check reference drift" });
    await shared.waitFor();
    await ben.page.route("**/api/v1" + detail, (route) => route.abort(), { times: 1 });
    await shared.click();
    await ben.page.getByRole("alert").waitFor();
    check(
      (await shared.isVisible()) &&
        (await discussion.getByLabel("New task comment", { exact: true }).inputValue()) ===
          "Unsent uncertainty question",
      base + " failed catch-up keeps hint and draft",
    );
    // Reconnect catches a change made while the browser transport is offline.
    const subscriptionsBefore = ben.frames.filter((f) => f.type === "subscribed").length;
    await ben.page.evaluate(() => window.__reviewSockets.at(-1).close());
    task = await call(asha, detail, { ...fields(task), title: "Offline reviewed experiment" }, "PUT");
    await until(() => ben.frames.filter((f) => f.type === "subscribed").length > subscriptionsBefore);
    await ben.page.getByText("Live", { exact: true }).waitFor();
    await shared.waitFor();
    await shared.click();
    await ben.page.getByRole("heading", { name: "Offline reviewed experiment", exact: true }).waitFor();
    check(
      (await discussion.getByLabel("New task comment", { exact: true }).inputValue()) ===
        "Unsent uncertainty question",
      base + " reconnect catch-up preserves draft",
    );
    check(
      ben.frames
        .filter((f) => f.type === "tasks.changed")
        .every(
          (f) => Object.keys(f).sort().join(",") === "type,workspace_id" && f.workspace_id === section.id,
        ),
      base + " received hints contain only actual workspace scope",
    );
    check(
      !chen.frames.some((f) => f.type === "tasks.changed" && f.workspace_id === section.id),
      base + " sibling subscriber receives no section hints",
    );
    // Assignment changes notify My Tasks without exposing assignment metadata in events.
    await ben.page.goto(origin + base + "/my-tasks");
    await ben.page.getByRole("button", { name: "Refresh My Tasks", exact: true }).click();
    await call(asha, detail + "/assignee", { revision: task.revision, user_id: ben.session.user.id }, "PUT");
    await ben.page
      .getByText("Shared assignments may have changed. Refresh My Tasks to check current work.", {
        exact: true,
      })
      .waitFor();
    await ben.page.getByRole("button", { name: "Refresh My Tasks", exact: true }).click();
    await ben.page.getByRole("heading", { name: "Offline reviewed experiment", exact: true }).waitFor();
    check(true, base + " My Tasks catches new shared responsibility");
    // More than one task page: updating visible cards must not jump to page one.
    for (let i = 0; i < 26; i++)
      await call(asha, path, { client_id: crypto.randomUUID(), title: "Paged experiment " + i });
    await ben.page.goto(origin + base + `/w/${section.id}/todos`);
    await ben.page.getByRole("button", { name: list.title, exact: true }).click();
    const nextPage = ben.page.waitForResponse(
      (r) => r.request().method() === "GET" && r.url().includes(path + "?after="),
    );
    await ben.page.getByRole("button", { name: "More tasks", exact: true }).click();
    await nextPage;
    await ben.page.getByText("Loading tasks…", { exact: true }).waitFor({ state: "hidden" });
    const pagedCard = ben.page.locator(".todo-task-list > li").first(),
      pagedTitle = await pagedCard.getByRole("heading", { level: 4 }).innerText();
    await pagedCard.getByRole("button", { name: "View comments", exact: true }).click();
    await pagedCard.getByLabel("New task comment", { exact: true }).fill("Keep my second-page draft");
    await call(asha, detail + "/comments", { client_id: crypto.randomUUID(), body: "Pagination review" });
    await shared.waitFor();
    await shared.click();
    await ben.page.getByText("Displayed tasks checked.", { exact: false }).waitFor();
    check(
      (await ben.page
        .locator(".todo-task-list > li")
        .first()
        .getByRole("heading", { level: 4 })
        .innerText()) === pagedTitle &&
        (await ben.page.getByLabel("New task comment", { exact: true }).inputValue()) ===
          "Keep my second-page draft",
      base + " catch-up retains second-page card and comment draft",
    );
    await admin.ctx.request.delete(
      admin.api + `/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,
      { headers: admin.headers },
    );
    await ben.page.getByLabel("New task comment", { exact: true }).waitFor({ state: "hidden" });
    check(
      (await ben.page.locator(".todo-task-list > li").count()) === 0,
      base + " revocation clears shared cards and composers",
    );
    check(
      ben.errors.length === 0 && asha.errors.length === 0 && chen.errors.length === 0,
      base + " no browser exceptions",
    );
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${checks} task update browser checks passed`);
} finally {
  await browser.close();
}
