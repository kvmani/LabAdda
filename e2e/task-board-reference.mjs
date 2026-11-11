// C3 board context: use disposable proxy fixtures; source access revoked last.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let count = 0;
function check(value, label) {
  assert.ok(value, label);
  count++;
  console.log("PASS " + label);
}
async function login(base, name) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }),
    page = await ctx.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Sign out" }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return {
    ctx,
    page,
    session,
    errors,
    api: origin + base + "/api/v1",
    headers: { "X-CSRF-Token": session.csrf_token },
  };
}
async function call(user, path, data, method = data ? "POST" : "GET") {
  const result = await user.ctx.request.fetch(user.api + path, { method, headers: user.headers, data });
  assert.ok(result.ok(), await result.text());
  return result.json();
}
async function list(user, workspace, title) {
  return call(user, "/todos/lists", { client_id: crypto.randomUUID(), title, workspace_id: workspace });
}
async function ink(user, workspace, epoch = 1) {
  return call(user, `/workspaces/${workspace}/board/ops`, {
    epoch,
    type: "add",
    op_id: crypto.randomUUID(),
    object_id: crypto.randomUUID(),
    payload: {
      kind: "stroke",
      data: {
        points: [
          [80, 90],
          [140, 100],
          [180, 140],
        ],
        color: "#1565c0",
        width: 3,
      },
    },
  });
}
async function openBoard(user, base, workspace, epoch) {
  await user.page.goto(origin + base + `/w/${workspace}/board`);
  await user.page
    .locator(".toolbar")
    .getByText(new RegExp("Epoch " + epoch + " · rev"))
    .waitFor();
  await user.page.getByRole("button", { name: "Create task from board", exact: true }).click();
  return user.page.getByRole("form", { name: "Create task from board", exact: true });
}
async function openTasks(user, base, workspace, row) {
  await user.page.goto(origin + base + (workspace ? `/w/${workspace}/todos` : "/todos"));
  await user.page.getByRole("button", { name: row.title, exact: true }).click();
}
async function accessible(user, base, label) {
  for (const width of [1400, 390]) {
    await user.page.setViewportSize({ width, height: 1100 });
    await user.page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
    const violations = await user.page.evaluate(async () =>
      (
        await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
        })
      ).violations.map((v) => v.id),
    );
    check(
      violations.length === 0,
      base + " " + label + " accessibility " + width + " " + violations.join(","),
    );
    check(
      await user.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      base + " " + label + " no overflow " + width,
    );
  }
  await user.page.setViewportSize({ width: 1400, height: 1100 });
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const ben = await login(base, "ben"),
      asha = await login(base, "asha"),
      chen = await login(base, "chen"),
      admin = await login(base, "admin");
    const spaces = (await call(ben, "/workspaces")).workspaces,
      section = spaces.find((w) => w.name === "Thin Films Section"),
      division = spaces.find((w) => w.name === "Surface Science Division");
    const privateList = await list(ben, null, "My plan actions"),
      sharedList = await list(ben, division.id, "Division plan actions");
    await ink(asha, section.id);
    let form = await openBoard(ben, base, section.id, 1);
    await form.getByLabel("Task destination", { exact: true }).selectOption("personal");
    await form.getByLabel("Destination list", { exact: true }).selectOption(privateList.id);
    await form.getByLabel("Task title", { exact: true }).fill("Review research controls");
    await form
      .getByLabel("Task description", { exact: true })
      .fill("Repeat blank and witness controls before the next film series.");
    check(
      await form.getByText("Reviewed board context: epoch 1, revision 1.", { exact: false }).isVisible(),
      base + " task form pins reviewed epoch and revision",
    );
    await accessible(ben, base, "board task form");
    await ink(asha, section.id);
    await form.getByRole("button", { name: "Save board task", exact: true }).click();
    await form
      .getByText("The board changed. Review its latest context before creating this task.", { exact: true })
      .waitFor();
    check(
      (await form.getByRole("button", { name: "Save board task", exact: true }).isDisabled()) &&
        (await form.getByLabel("Task title", { exact: true }).inputValue()) === "Review research controls",
      base + " stale context blocks creation and retains reviewed draft",
    );
    await form.getByRole("button", { name: "Load latest board context (keeps draft)", exact: true }).click();
    await form.getByText("Reviewed board context: epoch 1, revision 2.", { exact: false }).waitFor();
    check(
      (await form.getByLabel("Task description", { exact: true }).inputValue()) ===
        "Repeat blank and witness controls before the next film series.",
      base + " explicit latest context keeps task text",
    );
    await ben.page.route(
      "**/api/v1/todos/lists/*/from-board",
      async (route) => {
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await form.getByRole("button", { name: "Save board task", exact: true }).click();
    await form.getByRole("button", { name: "Retry same task copy", exact: true }).waitFor();
    await ink(asha, section.id);
    check(
      (await form.getByLabel("Task title", { exact: true }).isDisabled()) &&
        (await form.getByLabel("Task destination", { exact: true }).isDisabled()),
      base + " unknown write freezes context text and destination",
    );
    await form.getByRole("button", { name: "Retry same task copy", exact: true }).click();
    await ben.page
      .getByText("Task saved. Its source link still requires access to the original board.", { exact: true })
      .waitFor();
    const saved = (await call(ben, `/todos/lists/${privateList.id}/tasks`)).items;
    check(saved.length === 1, base + " retry after later ink recovers one task");
    await openTasks(ben, base, null, privateList);
    await ben.page.getByRole("button", { name: "View source reference", exact: true }).click();
    await ben.page.getByText("Recorded context: epoch 1, revision 2.", { exact: true }).waitFor();
    check(
      await ben.page.getByText("Current board: epoch 1, revision 3.", { exact: false }).isVisible(),
      base + " source view separates recorded context from live board",
    );
    check(
      (await ben.page.getByRole("link", { name: "Open source board", exact: true }).getAttribute("href")) ===
        base + `/w/${section.id}/board`,
      base + " live board link preserves URL prefix",
    );
    await accessible(ben, base, "protected board source");
    await call(asha, `/workspaces/${section.id}/board/restore`, { revision: 1 });
    await ben.page.getByRole("button", { name: "View source reference", exact: true }).click();
    await ben.page.getByText("Current board: epoch 2, revision", { exact: false }).waitFor();
    check(
      await ben.page.getByText("Recorded context: epoch 1, revision 2.", { exact: true }).isVisible(),
      base + " restore does not rewrite recorded task context",
    );
    form = await openBoard(ben, base, section.id, 2);
    await form.getByLabel("Task destination", { exact: true }).selectOption(division.id);
    await form.getByLabel("Destination list", { exact: true }).selectOption(sharedList.id);
    await form.getByLabel("Task title", { exact: true }).fill("Reviewed division research action");
    check(
      await form.getByRole("button", { name: "Save board task", exact: true }).isDisabled(),
      base + " different audience requires explicit task-text confirmation",
    );
    await form.getByRole("checkbox").check();
    await form.getByRole("button", { name: "Save board task", exact: true }).click();
    await ben.page
      .getByText("Task saved. Its source link still requires access to the original board.", { exact: true })
      .waitFor();
    const shared = (await call(ben, `/todos/lists/${sharedList.id}/tasks`)).items[0],
      sourcePath = `/todos/lists/${sharedList.id}/tasks/${shared.id}/source`;
    await openTasks(chen, base, division.id, sharedList);
    await chen.page.getByRole("button", { name: "View source reference", exact: true }).click();
    await chen.page.getByText("Source unavailable or no longer accessible.", { exact: true }).waitFor();
    check(
      (await chen.page.getByText("Recorded context:", { exact: false }).count()) === 0 &&
        (await chen.ctx.request.get(chen.api + sourcePath)).status() === 404,
      base + " sibling cannot retrieve protected board context",
    );
    // A successful source response held before grant loss must never restore context.
    await openTasks(ben, base, division.id, sharedList);
    let release, captured;
    const hold = new Promise((resolve) => (release = resolve)),
      ready = new Promise((resolve) => (captured = resolve));
    await ben.page.route(
      "**/api/v1" + sourcePath,
      async (route) => {
        const response = await route.fetch();
        captured();
        await hold;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    const delivered = ben.page.waitForResponse((r) => r.url().endsWith(sourcePath));
    await ben.page.getByRole("button", { name: "View source reference", exact: true }).click();
    await ready;
    await call(
      admin,
      `/admin/workspaces/${division.id}/memberships`,
      { user_id: ben.session.user.id, role: "member" },
      "PUT",
    );
    await call(
      admin,
      `/admin/workspaces/${section.id}/memberships/${ben.session.user.id}`,
      undefined,
      "DELETE",
    );
    await ben.page.getByText("Source unavailable or no longer accessible.", { exact: true }).waitFor();
    await ben.page.evaluate(() => {
      window.__contextLeaked = false;
      new MutationObserver(() => {
        if (document.body.innerText.includes("Recorded context:")) window.__contextLeaked = true;
      }).observe(document.body, { childList: true, subtree: true, characterData: true });
    });
    release();
    await (await delivered).finished();
    await ben.page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );
    check(
      !(await ben.page.evaluate(() => window.__contextLeaked)),
      base + " delayed source cannot restore revoked board metadata",
    );
    check(
      (await call(ben, `/todos/lists/${sharedList.id}/tasks`)).items.length === 1,
      base + " reviewed task survives source-only access loss",
    );
    check(
      ben.errors.length === 0 && asha.errors.length === 0 && chen.errors.length === 0,
      base + " no browser exceptions",
    );
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${count} board reference browser checks passed`);
} catch (error) {
  for (const [i, ctx] of browser.contexts().entries())
    for (const page of ctx.pages()) {
      await page.screenshot({ path: `/tmp/board-reference-failure-${i}.png`, fullPage: true });
      console.error((await page.locator("main").innerText()).slice(-3000));
    }
  throw error;
} finally {
  await browser.close();
}
