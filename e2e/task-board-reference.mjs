// C3 board context: use disposable proxy fixtures; source access revoked last.
import {
  bases,
  call,
  holdFirstResponse,
  loseNextResponse,
  nextPaint,
  origin,
  startHarness,
} from "./lib/harness.mjs";

const harness = await startHarness();
const { check, checkLayouts, login } = harness;

const sourceUnavailable = "Source unavailable or no longer accessible.";
const savedNotice = "Task saved. Its source link still requires access to the original board.";

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const labelled = (scope, label) => scope.getByLabel(label, { exact: true });
const saveButton = (form) => buttonNamed(form, "Save board task");
const viewSourceButton = (page) => buttonNamed(page, "View source reference");

function createList(user, workspaceId, title) {
  return call(user, "/todos/lists", { client_id: crypto.randomUUID(), title, workspace_id: workspaceId });
}

function addStroke(user, workspaceId, epoch = 1) {
  return call(user, `/workspaces/${workspaceId}/board/ops`, {
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

async function openBoardForm(user, base, workspaceId, epoch) {
  await user.page.goto(origin + base + `/w/${workspaceId}/board`);
  await user.page
    .locator(".toolbar")
    .getByText(new RegExp("Epoch " + epoch + " · rev"))
    .waitFor();
  await buttonNamed(user.page, "Create task from board").click();
  return user.page.getByRole("form", { name: "Create task from board", exact: true });
}

async function openTaskList(user, base, workspaceId, list) {
  await user.page.goto(origin + base + (workspaceId ? `/w/${workspaceId}/todos` : "/todos"));
  await buttonNamed(user.page, list.title).click();
}

async function checkStaleContext(ben, asha, base, section, privateList) {
  const form = await openBoardForm(ben, base, section.id, 1);
  await labelled(form, "Task destination").selectOption("personal");
  await labelled(form, "Destination list").selectOption(privateList.id);
  await labelled(form, "Task title").fill("Review research controls");
  await labelled(form, "Task description").fill(
    "Repeat blank and witness controls before the next film series.",
  );
  check(
    await form.getByText("Reviewed board context: epoch 1, revision 1.", { exact: false }).isVisible(),
    base + " task form pins reviewed epoch and revision",
  );
  await checkLayouts(ben, base, "board task form");
  await addStroke(asha, section.id);
  await saveButton(form).click();
  await form
    .getByText("The board changed. Review its latest context before creating this task.", { exact: true })
    .waitFor();
  check(
    (await saveButton(form).isDisabled()) &&
      (await labelled(form, "Task title").inputValue()) === "Review research controls",
    base + " stale context blocks creation and retains reviewed draft",
  );
  await buttonNamed(form, "Load latest board context (keeps draft)").click();
  await form.getByText("Reviewed board context: epoch 1, revision 2.", { exact: false }).waitFor();
  check(
    (await labelled(form, "Task description").inputValue()) ===
      "Repeat blank and witness controls before the next film series.",
    base + " explicit latest context keeps task text",
  );
  return form;
}

async function checkLostWriteRecovery(ben, asha, base, form, privateList, section) {
  await loseNextResponse(ben.page, "**/api/v1/todos/lists/*/from-board");
  await saveButton(form).click();
  await buttonNamed(form, "Retry same task copy").waitFor();
  await addStroke(asha, section.id);
  check(
    (await labelled(form, "Task title").isDisabled()) &&
      (await labelled(form, "Task destination").isDisabled()),
    base + " unknown write freezes context text and destination",
  );
  await buttonNamed(form, "Retry same task copy").click();
  await ben.page.getByText(savedNotice, { exact: true }).waitFor();
  const saved = (await call(ben, `/todos/lists/${privateList.id}/tasks`)).items;
  check(saved.length === 1, base + " retry after later ink recovers one task");
}

async function checkSourceViewAndRestore(ben, asha, base, section, privateList) {
  await openTaskList(ben, base, null, privateList);
  await viewSourceButton(ben.page).click();
  await ben.page.getByText("Recorded context: epoch 1, revision 2.", { exact: true }).waitFor();
  check(
    await ben.page.getByText("Current board: epoch 1, revision 3.", { exact: false }).isVisible(),
    base + " source view separates recorded context from live board",
  );
  const href = await ben.page
    .getByRole("link", { name: "Open source board", exact: true })
    .getAttribute("href");
  check(href === base + `/w/${section.id}/board`, base + " live board link preserves URL prefix");
  await checkLayouts(ben, base, "protected board source");
  await call(asha, `/workspaces/${section.id}/board/restore`, { revision: 1 });
  await viewSourceButton(ben.page).click();
  await ben.page.getByText("Current board: epoch 2, revision", { exact: false }).waitFor();
  check(
    await ben.page.getByText("Recorded context: epoch 1, revision 2.", { exact: true }).isVisible(),
    base + " restore does not rewrite recorded task context",
  );
}

async function checkDivisionAudience(ben, chen, base, section, division, sharedList) {
  const form = await openBoardForm(ben, base, section.id, 2);
  await labelled(form, "Task destination").selectOption(division.id);
  await labelled(form, "Destination list").selectOption(sharedList.id);
  await labelled(form, "Task title").fill("Reviewed division research action");
  check(
    await saveButton(form).isDisabled(),
    base + " different audience requires explicit task-text confirmation",
  );
  await form.getByRole("checkbox").check();
  await saveButton(form).click();
  await ben.page.getByText(savedNotice, { exact: true }).waitFor();
  const shared = (await call(ben, `/todos/lists/${sharedList.id}/tasks`)).items[0];
  const sourcePath = `/todos/lists/${sharedList.id}/tasks/${shared.id}/source`;
  await openTaskList(chen, base, division.id, sharedList);
  await viewSourceButton(chen.page).click();
  await chen.page.getByText(sourceUnavailable, { exact: true }).waitFor();
  const contextShown = await chen.page.getByText("Recorded context:", { exact: false }).count();
  const direct = await chen.ctx.request.get(chen.api + sourcePath);
  check(
    contextShown === 0 && direct.status() === 404,
    base + " sibling cannot retrieve protected board context",
  );
  return sourcePath;
}

async function checkHeldSourceAfterRevocation(ben, admin, base, ctx, sourcePath) {
  // A successful source response held before grant loss must never restore context.
  const { section, division, sharedList } = ctx;
  const page = ben.page;
  await openTaskList(ben, base, division.id, sharedList);
  const heldSource = await holdFirstResponse(page, "**/api/v1" + sourcePath);
  await viewSourceButton(page).click();
  await heldSource.captured;
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
  await page.getByText(sourceUnavailable, { exact: true }).waitFor();
  await page.evaluate(() => {
    window.__contextLeaked = false;
    new MutationObserver(() => {
      if (document.body.innerText.includes("Recorded context:")) window.__contextLeaked = true;
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  const delivered = page.waitForResponse((response) => response.url().endsWith(sourcePath));
  heldSource.release();
  await (await delivered).finished();
  await nextPaint(page);
  check(
    !(await page.evaluate(() => window.__contextLeaked)),
    base + " delayed source cannot restore revoked board metadata",
  );
  const remaining = (await call(ben, `/todos/lists/${sharedList.id}/tasks`)).items;
  check(remaining.length === 1, base + " reviewed task survives source-only access loss");
}

async function saveFailureScreenshots() {
  for (const [index, context] of harness.browser.contexts().entries()) {
    for (const page of context.pages()) {
      await page.screenshot({ path: `/tmp/board-reference-failure-${index}.png`, fullPage: true });
      console.error((await page.locator("main").innerText()).slice(-3000));
    }
  }
}

try {
  for (const base of bases) {
    const ben = await login(base, "ben");
    const asha = await login(base, "asha");
    const chen = await login(base, "chen");
    const admin = await login(base, "admin");
    const spaces = (await call(ben, "/workspaces")).workspaces;
    const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
    const division = spaces.find((workspace) => workspace.name === "Surface Science Division");
    const privateList = await createList(ben, null, "My plan actions");
    const sharedList = await createList(ben, division.id, "Division plan actions");
    await addStroke(asha, section.id);
    const form = await checkStaleContext(ben, asha, base, section, privateList);
    await checkLostWriteRecovery(ben, asha, base, form, privateList, section);
    await checkSourceViewAndRestore(ben, asha, base, section, privateList);
    const sourcePath = await checkDivisionAudience(ben, chen, base, section, division, sharedList);
    await checkHeldSourceAfterRevocation(ben, admin, base, { section, division, sharedList }, sourcePath);
    check(
      ben.errors.length === 0 && asha.errors.length === 0 && chen.errors.length === 0,
      base + " no browser exceptions",
    );
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} board reference browser checks passed`);
} catch (error) {
  await saveFailureScreenshots();
  throw error;
} finally {
  await harness.close();
}
