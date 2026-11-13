// C2 content-free hints and explicit catch-up, on fresh disposable proxy fixtures.
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import {
  bases,
  call,
  frameMark,
  holdFirstResponse,
  origin,
  startHarness,
  waitForFrame,
} from "./lib/harness.mjs";

const outputDir = process.argv[2] ? resolve(process.argv[2]) : null;
if (outputDir) mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { check, login } = harness;

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const taskTitleBox = (page) => page.getByLabel("Task title", { exact: true });
const commentBox = (scope) => scope.getByLabel("New task comment", { exact: true });
const headingNamed = (page, name) => page.getByRole("heading", { name, exact: true });
const hintsOf = (user) => user.sockets.frames.filter((frame) => frame.type === "tasks.changed");
const taskFields = (task) =>
  Object.fromEntries(
    ["title", "description", "due_date", "priority", "checklist", "done", "status", "revision"].map((key) => [
      key,
      task[key],
    ]),
  );

async function openList(user, base, workspaceId, list) {
  await user.page.goto(origin + base + `/w/${workspaceId}/todos`);
  await buttonNamed(user.page, list.title).click();
  await headingNamed(user.page, "Plan experiment").waitFor();
}

/** Opens the panels whose unsent drafts the later steps must not lose. */
async function openDraftsOnCard(bharat) {
  const page = bharat.page;
  await buttonNamed(page, "View comments").click();
  const discussion = page.getByRole("region", { name: "Task comments", exact: true });
  await discussion.getByText("No comments yet.", { exact: true }).waitFor();
  await commentBox(discussion).fill("Unsent uncertainty question");
  await buttonNamed(page, "Edit task: Plan experiment").click();
  await taskTitleBox(page).fill("Unsent editor draft");
  const assignment = page.getByRole("region", { name: "Task assignment", exact: true });
  await buttonNamed(assignment, "Change assignee").click();
  await assignment.getByLabel("Assignee", { exact: true }).selectOption(bharat.session.user.id);
  return { discussion, assignment };
}

async function checkDraftsSurviveCatchUp(bharat, shared, panels, base) {
  const { discussion, assignment } = panels;
  const page = bharat.page;
  await shared.waitFor();
  check(
    (await taskTitleBox(page).inputValue()) === "Unsent editor draft",
    base + " hint does not replace task draft",
  );
  await shared.click();
  await headingNamed(page, "Reviewed experiment").waitFor();
  check(
    (await commentBox(discussion).inputValue()) === "Unsent uncertainty question",
    base + " visible-card refresh preserves discussion draft",
  );
  const choice = await assignment.getByLabel("Assignee", { exact: true }).inputValue();
  const saveDisabled = await buttonNamed(assignment, "Save assignment").isDisabled();
  check(
    choice === bharat.session.user.id && saveDisabled,
    base + " changed revision preserves choice and requires assignment review",
  );
  if (outputDir && base === "") {
    await page.screenshot({ path: outputDir + "/shared-task-drafts.png", fullPage: true });
  }
  await buttonNamed(assignment, "Reload task assignment").click();
  await buttonNamed(assignment, "Change assignee").waitFor();
  check(
    (await taskTitleBox(page).inputValue()) === "Unsent editor draft",
    base + " refresh keeps task editor draft and original write revision",
  );
  await buttonNamed(page, "Save task").click();
  await page
    .getByText("This task changed. Refresh and review before saving again.", { exact: true })
    .waitFor();
  check(
    (await taskTitleBox(page).inputValue()) === "Unsent editor draft",
    base + " stale editor cannot overwrite the reviewed remote revision",
  );
  await buttonNamed(page, "Close editor").click();
}

async function checkDiscussionCatchUp(bharat, asha, discussion, detail, base) {
  await call(asha, detail + "/comments", {
    client_id: crypto.randomUUID(),
    body: "Controls agreed by colleague",
  });
  await discussion
    .getByText("Shared discussion may have changed. Refresh comments; your draft is kept.", { exact: true })
    .waitFor();
  await buttonNamed(discussion, "Refresh comments").click();
  await discussion.getByText("Controls agreed by colleague", { exact: true }).waitFor();
  check(
    (await commentBox(discussion).inputValue()) === "Unsent uncertainty question",
    base + " discussion catch-up keeps typed text",
  );
}

async function checkNewerSignalStaysPending(bharat, asha, shared, detail, task, base) {
  // A hint while the HTTP snapshot is in flight cannot be acknowledged by that older response.
  const page = bharat.page;
  const heldSnapshot = await holdFirstResponse(page, "**/api/v1" + detail);
  await shared.click();
  await heldSnapshot.captured;
  const beforeHint = frameMark(bharat);
  const updated = await call(
    asha,
    detail,
    { ...taskFields(task), title: "Second reviewed experiment" },
    "PUT",
  );
  await waitForFrame(bharat, (frame) => frame.type === "tasks.changed", beforeHint);
  heldSnapshot.release();
  await page.waitForFunction(() =>
    [...document.querySelectorAll("button")].some(
      (button) => button.textContent === "Check shared updates" && !button.disabled,
    ),
  );
  await shared.waitFor();
  check(await shared.isVisible(), base + " in-flight newer signal stays pending");
  await shared.click();
  await headingNamed(page, "Second reviewed experiment").waitFor();
  await shared.waitFor({ state: "hidden" });
  return updated;
}

async function checkFailedCatchUp(bharat, asha, shared, discussion, detail, base) {
  // A failed authorized read leaves the hint pending and the draft available.
  await call(asha, detail + "/comments", { client_id: crypto.randomUUID(), body: "Check reference drift" });
  await shared.waitFor();
  await bharat.page.route("**/api/v1" + detail, (route) => route.abort(), { times: 1 });
  await shared.click();
  await bharat.page.getByRole("alert").waitFor();
  check(
    (await shared.isVisible()) &&
      (await commentBox(discussion).inputValue()) === "Unsent uncertainty question",
    base + " failed catch-up keeps hint and draft",
  );
}

async function checkReconnectCatchUp(bharat, asha, shared, discussion, detail, task, base) {
  // Reconnect catches a change made while the browser transport is offline.
  const beforeClose = frameMark(bharat);
  await bharat.page.evaluate(() => window.__sockets.at(-1).close());
  const updated = await call(
    asha,
    detail,
    { ...taskFields(task), title: "Offline reviewed experiment" },
    "PUT",
  );
  await waitForFrame(bharat, (frame) => frame.type === "subscribed", beforeClose);
  await bharat.page.getByText("Live", { exact: true }).waitFor();
  await shared.waitFor();
  await shared.click();
  await headingNamed(bharat.page, "Offline reviewed experiment").waitFor();
  check(
    (await commentBox(discussion).inputValue()) === "Unsent uncertainty question",
    base + " reconnect catch-up preserves draft",
  );
  return updated;
}

function checkHintScope(bharat, chitra, section, base) {
  const scopedToSection = hintsOf(bharat).every(
    (frame) =>
      Object.keys(frame).sort().join(",") === "type,workspace_id" && frame.workspace_id === section.id,
  );
  check(scopedToSection, base + " received hints contain only actual workspace scope");
  const chitraHints = hintsOf(chitra).filter((frame) => frame.workspace_id === section.id);
  check(chitraHints.length === 0, base + " sibling subscriber receives no section hints");
}

async function checkMyTasksCatchesAssignment(bharat, asha, detail, task, base) {
  // Assignment changes notify My Tasks without exposing assignment metadata in events.
  const page = bharat.page;
  await page.goto(origin + base + "/my-tasks");
  await buttonNamed(page, "Refresh My Tasks").click();
  await call(asha, detail + "/assignee", { revision: task.revision, user_id: bharat.session.user.id }, "PUT");
  await page
    .getByText("Shared assignments may have changed. Refresh My Tasks to check current work.", {
      exact: true,
    })
    .waitFor();
  await buttonNamed(page, "Refresh My Tasks").click();
  await headingNamed(page, "Offline reviewed experiment").waitFor();
  check(true, base + " My Tasks catches new shared responsibility");
}

async function checkSecondPageCatchUp(bharat, asha, shared, section, list, detail, base) {
  // More than one task page: updating visible cards must not jump to page one.
  const page = bharat.page;
  const path = `/todos/lists/${list.id}/tasks`;
  for (let index = 0; index < 26; index++) {
    await call(asha, path, { client_id: crypto.randomUUID(), title: "Paged experiment " + index });
  }
  await page.goto(origin + base + `/w/${section.id}/todos`);
  await buttonNamed(page, list.title).click();
  const nextPage = page.waitForResponse(
    (response) => response.request().method() === "GET" && response.url().includes(path + "?after="),
  );
  await buttonNamed(page, "More tasks").click();
  await nextPage;
  await page.getByText("Loading tasks…", { exact: true }).waitFor({ state: "hidden" });
  const firstCard = page.locator(".todo-task-list > li").first();
  const firstTitle = await firstCard.getByRole("heading", { level: 4 }).innerText();
  await buttonNamed(firstCard, "View comments").click();
  await commentBox(firstCard).fill("Keep my second-page draft");
  await call(asha, detail + "/comments", { client_id: crypto.randomUUID(), body: "Pagination review" });
  await shared.waitFor();
  await shared.click();
  await page.getByText("Displayed tasks checked.", { exact: false }).waitFor();
  const titleAfter = await page
    .locator(".todo-task-list > li")
    .first()
    .getByRole("heading", { level: 4 })
    .innerText();
  check(
    titleAfter === firstTitle && (await commentBox(page).inputValue()) === "Keep my second-page draft",
    base + " catch-up retains second-page card and comment draft",
  );
}

async function checkRevocation(bharat, admin, section, base) {
  await admin.ctx.request.delete(
    admin.api + `/admin/workspaces/${section.id}/memberships/${bharat.session.user.id}`,
    { headers: admin.headers },
  );
  await commentBox(bharat.page).waitFor({ state: "hidden" });
  const cards = await bharat.page.locator(".todo-task-list > li").count();
  check(cards === 0, base + " revocation clears shared cards and composers");
}

try {
  for (const base of bases) {
    const bharat = await login(base, "bharat", { trackSockets: true });
    const asha = await login(base, "asha");
    const chitra = await login(base, "chitra", { trackSockets: true });
    const admin = await login(base, "admin");
    const spaces = (await call(bharat, "/workspaces")).workspaces;
    const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
    const list = await call(asha, "/todos/lists", {
      client_id: crypto.randomUUID(),
      title: "Live project actions",
      workspace_id: section.id,
    });
    const path = `/todos/lists/${list.id}/tasks`;
    let task = await call(asha, path, { client_id: crypto.randomUUID(), title: "Plan experiment" });
    const detail = path + "/" + task.id;
    await openList(bharat, base, section.id, list);
    const shared = buttonNamed(bharat.page, "Check shared updates");
    // Opening the list alone must not raise the notice; a real change does.
    await bharat.page.waitForTimeout(1000);
    check((await shared.count()) === 0, base + " opening a list shows no shared-update notice");
    task = await call(asha, detail, taskFields(task), "PUT");
    await shared.waitFor();
    await shared.click();
    await shared.waitFor({ state: "hidden" });
    const panels = await openDraftsOnCard(bharat);
    task = await call(asha, detail, { ...taskFields(task), title: "Reviewed experiment" }, "PUT");
    await checkDraftsSurviveCatchUp(bharat, shared, panels, base);
    await checkDiscussionCatchUp(bharat, asha, panels.discussion, detail, base);
    task = await checkNewerSignalStaysPending(bharat, asha, shared, detail, task, base);
    await checkFailedCatchUp(bharat, asha, shared, panels.discussion, detail, base);
    task = await checkReconnectCatchUp(bharat, asha, shared, panels.discussion, detail, task, base);
    checkHintScope(bharat, chitra, section, base);
    await checkMyTasksCatchesAssignment(bharat, asha, detail, task, base);
    await checkSecondPageCatchUp(bharat, asha, shared, section, list, detail, base);
    await checkRevocation(bharat, admin, section, base);
    check(
      bharat.errors.length === 0 && asha.errors.length === 0 && chitra.errors.length === 0,
      base + " no browser exceptions",
    );
    await Promise.all([bharat.ctx.close(), asha.ctx.close(), chitra.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} task update browser checks passed`);
} finally {
  await harness.close();
}
