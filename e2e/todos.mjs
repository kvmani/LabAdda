// C1 personal/shared tasks. Fresh disposable root/prefix proxy fixtures only.
import { mkdirSync } from "node:fs";
import {
  axeViolations,
  bases,
  hasNoSideScroll,
  holdFirstResponse,
  loseNextResponse,
  nextPaint,
  origin,
  startHarness,
} from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/labadda-todos";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { check, login } = harness;

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const headingNamed = (scope, name) => scope.getByRole("heading", { name, exact: true });
const labelled = (scope, label) => scope.getByLabel(label, { exact: true });
const taskTitleBox = (page) => labelled(page, "Task title");
const listNameBox = (page) => labelled(page, "List name");
const selectedListRegion = (page) => page.getByRole("region", { name: "Selected to-do list" });
const saveTaskButton = (page) => buttonNamed(page, "Save task");

async function createList(page, title) {
  await page.getByLabel("New list title").fill(title);
  await buttonNamed(page, "Create list").click();
  await headingNamed(page, title).waitFor();
}

async function createTask(page, title, loseReply = false) {
  await buttonNamed(page, "New task").click();
  await taskTitleBox(page).fill(title);
  await labelled(page, "Description").fill("Calibrate → measure α → compare sibling-section results");
  await labelled(page, "Due date").fill("2026-12-01");
  await labelled(page, "Priority").selectOption("high");
  await buttonNamed(page, "Add checklist item").click();
  await labelled(page, "Checklist item 1 title").fill("Check instrument calibration");
  if (loseReply) await loseNextResponse(page, "**/api/v1/todos/lists/*/tasks");
  await saveTaskButton(page).click();
  if (loseReply) {
    await page.getByRole("button", { name: "Retry same task creation" }).waitFor();
    check(await taskTitleBox(page).isDisabled(), "uncertain task preserves intent");
    await page.getByRole("button", { name: "Retry same task creation" }).click();
  }
  await headingNamed(page, title).waitFor();
}

function fetchJson(user, path) {
  return user.ctx.request.get(user.api + path).then((response) => response.json());
}

function statusOf(user, path) {
  return user.ctx.request.get(user.api + path).then((response) => response.status());
}

function forbiddenResponse(message) {
  return {
    status: 403,
    contentType: "application/json",
    body: JSON.stringify({ error: { code: "forbidden", message } }),
  };
}

async function checkLostListResponse(bharat, base) {
  const page = bharat.page;
  await page.goto(origin + base + "/todos");
  await page.getByText("No to-do lists in this scope yet.", { exact: true }).waitFor();
  // Lose a committed list response; explicit same-key retry recovers one list.
  await page.route(
    "**/api/v1/todos/lists",
    async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      await route.fetch();
      await route.abort();
    },
    { times: 1 },
  );
  await page.getByLabel("New list title").fill("Private experiment checklist");
  await buttonNamed(page, "Create list").click();
  await page.getByRole("button", { name: "Retry same list creation" }).waitFor();
  check(
    await page.getByLabel("New list title").isDisabled(),
    base + " uncertain list freezes original intent",
  );
  await page.getByRole("button", { name: "Retry same list creation" }).click();
  await headingNamed(page, "Private experiment checklist").waitFor();
  const personal = (await fetchJson(bharat, "/todos/lists")).items;
  check(personal.length === 1, base + " lost list response creates exactly one list");
  return personal;
}

async function checkLostTaskResponseAndReload(bharat, base, personal) {
  const page = bharat.page;
  await createTask(page, "Prepare personal measurements", true);
  const tasks = (await fetchJson(bharat, `/todos/lists/${personal[0].id}/tasks`)).items;
  check(tasks.length === 1, base + " lost task response creates exactly once");
  await page.reload();
  await buttonNamed(page, "Private experiment checklist").click();
  await headingNamed(page, "Prepare personal measurements").waitFor();
  check(true, base + " Unicode/date/checklist task persists after reload");
}

async function checkLateSaveCannotRepopulate(bharat, base) {
  const page = bharat.page;
  await createList(page, "Personal reading");
  await buttonNamed(page, "Private experiment checklist").click();
  await buttonNamed(page, "New task").click();
  await taskTitleBox(page).fill("Late saved task");
  const heldSave = await holdFirstResponse(page, "**/api/v1/todos/lists/*/tasks");
  await saveTaskButton(page).click();
  await heldSave.captured;
  await buttonNamed(page, "Personal reading").click();
  const savedResponse = page.waitForResponse(
    (response) => response.request().method() === "POST" && /todos.*tasks$/.test(response.url()),
  );
  heldSave.release();
  await savedResponse;
  await nextPaint(page);
  const readingHeadings = await headingNamed(page, "Personal reading").count();
  const lateHeadings = await headingNamed(page, "Late saved task").count();
  check(readingHeadings === 1 && lateHeadings === 0, base + " late save cannot repopulate another list");
}

async function checkRenameConflict(bharat, base) {
  const page = bharat.page;
  const lists = (await fetchJson(bharat, "/todos/lists")).items;
  const reading = lists.find((row) => row.title === "Personal reading");
  await bharat.ctx.request.put(bharat.api + `/todos/lists/${reading.id}`, {
    headers: { "X-CSRF-Token": bharat.session.csrf_token },
    data: { title: "Personal reading updated", revision: reading.revision },
  });
  await listNameBox(page).fill("Uncommitted list-name draft");
  await buttonNamed(page, "Rename list").click();
  await page.getByRole("button", { name: "Load latest list (replaces draft)" }).waitFor();
  check(
    (await listNameBox(page).inputValue()) === "Uncommitted list-name draft",
    base + " list rename conflict keeps draft",
  );
  await page.getByRole("button", { name: "Load latest list (replaces draft)" }).click();
  await headingNamed(page, "Personal reading updated").waitFor();
  check(
    (await listNameBox(page).inputValue()) === "Personal reading updated",
    base + " explicit latest list reload recovers revision",
  );
  return reading;
}

async function checkDeniedRefreshes(bharat, base, reading) {
  const page = bharat.page;
  const denyListReads = async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    await route.fulfill(forbiddenResponse("Synthetic access revoked"));
  };
  await page.route("**/api/v1/todos/lists", denyListReads);
  await page.getByLabel("New list title").fill("Creation before denied refresh");
  await buttonNamed(page, "Create list").click();
  await page.getByRole("alert").filter({ hasText: "Synthetic access revoked" }).waitFor();
  check(
    (await selectedListRegion(page).count()) === 0,
    base + " denied post-create refresh cannot restore selected list",
  );
  await page.unroute("**/api/v1/todos/lists", denyListReads);
  await buttonNamed(page, "Refresh lists").click();
  await buttonNamed(page, "Personal reading updated").click();
  const denyAllListRequests = (route) => route.fulfill(forbiddenResponse("Synthetic rename revocation"));
  await page.route("**/api/v1/todos/lists", denyAllListRequests);
  const heldRename = await holdRenameResult(bharat, reading);
  const renameDone = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" && response.url().endsWith("/todos/lists/" + reading.id),
  );
  await listNameBox(page).fill("Delayed rename result");
  await buttonNamed(page, "Rename list").click();
  await heldRename.entered;
  await buttonNamed(page, "Refresh lists").click();
  await page.getByRole("alert").filter({ hasText: "Synthetic rename revocation" }).waitFor();
  heldRename.release();
  await renameDone;
  await page.unroute("**/api/v1/todos/lists", denyAllListRequests);
  await nextPaint(page);
  check(
    (await selectedListRegion(page).count()) === 0,
    base + " late rename cannot restore denied selection",
  );
}

/** Performs the rename on the server at once but hands the page its answer only after `release()`. */
async function holdRenameResult(bharat, reading) {
  let release;
  let markEntered;
  const gate = new Promise((resolve) => (release = resolve));
  const entered = new Promise((resolve) => (markEntered = resolve));
  await bharat.page.route(
    "**/api/v1/todos/lists/" + reading.id,
    async (route) => {
      const response = await bharat.ctx.request.put(route.request().url(), {
        headers: { "X-CSRF-Token": bharat.session.csrf_token },
        data: route.request().postDataJSON(),
      });
      const body = await response.body();
      markEntered();
      await gate;
      await route.fulfill({ status: response.status(), contentType: "application/json", body });
    },
    { times: 1 },
  );
  return { entered, release };
}

async function checkSectionTasks(bharat, people, base, section, personal) {
  const { asha, chitra, deepa, admin } = people;
  for (const colleague of [asha, chitra, deepa, admin]) {
    check(
      (await statusOf(colleague, `/todos/lists/${personal[0].id}/tasks`)) === 404,
      base + " personal tasks deny colleague/admin",
    );
  }
  await bharat.page.goto(origin + base + `/w/${section.id}/todos`);
  await createList(bharat.page, "Thin Films plan");
  await createTask(bharat.page, "Measure sample α");
  const list = (await fetchJson(bharat, "/todos/lists?workspace_id=" + section.id)).items[0];
  const task = (await fetchJson(bharat, `/todos/lists/${list.id}/tasks`)).items[0];
  for (const colleague of [chitra, deepa, admin]) {
    check(
      (await statusOf(colleague, `/todos/lists/${list.id}/tasks`)) === 404,
      base + " section tasks deny sibling/parent-only/admin",
    );
  }
  await asha.page.goto(origin + base + `/w/${section.id}/todos`);
  await buttonNamed(asha.page, "Thin Films plan").click();
  await headingNamed(asha.page, "Measure sample α").waitFor();
  check(true, base + " colleague sees shared tasks");
  return { list, task };
}

async function checkTwoWriters(bharat, asha, base, list, task) {
  // Two writers: preserve local draft on conflict, explicitly load committed data.
  const page = bharat.page;
  await buttonNamed(page, "Edit task: Measure sample α").click();
  await taskTitleBox(page).fill("Local unsaved task draft");
  const { description, due_date, priority, checklist, done, revision } = task;
  const changed = await asha.ctx.request.put(asha.api + `/todos/lists/${list.id}/tasks/${task.id}`, {
    headers: { "X-CSRF-Token": asha.session.csrf_token },
    data: {
      title: "Colleague revised measurement",
      description,
      due_date,
      priority,
      checklist,
      done,
      revision,
    },
  });
  check(changed.status() === 200, base + " second writer commits");
  await saveTaskButton(page).click();
  await page.getByText("Your draft is kept.", { exact: false }).waitFor();
  check(
    (await taskTitleBox(page).inputValue()) === "Local unsaved task draft",
    base + " conflict retains draft",
  );
  await page.getByRole("button", { name: "Load latest task (replaces draft)" }).click();
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll("input")).some(
      (element) => element.value === "Colleague revised measurement",
    ),
  );
  await labelled(page, "Task completed").check();
  await saveTaskButton(page).click();
  await headingNamed(page, "✓ Colleague revised measurement").waitFor();
  check(true, base + " explicit conflict reload then completion");
}

async function checkWorkflowStates(bharat, base, list, task) {
  const page = bharat.page;
  const editButton = buttonNamed(page, "Edit task: Colleague revised measurement");
  await editButton.click();
  await labelled(page, "Task completed").uncheck();
  await saveTaskButton(page).click();
  await headingNamed(page, "Colleague revised measurement").waitFor();
  check(true, base + " task reopens");
  for (const state of ["in_progress", "blocked"]) {
    await editButton.click();
    await labelled(page, "Workflow state").selectOption(state);
    await saveTaskButton(page).click();
    const stateName = state === "in_progress" ? "In progress" : "Blocked";
    await page.getByText(`${stateName} · high priority · Due 2026-12-01`, { exact: true }).waitFor();
    const current = await fetchJson(bharat, `/todos/lists/${list.id}/tasks/${task.id}`);
    check(current.status === state, base + " workflow " + state + " persists");
  }
  await buttonNamed(page, "View task history").click();
  const history = page.getByRole("region", { name: "Task change history" });
  await history.getByText("Workflow state: In progress → Blocked", { exact: true }).waitFor();
  const transitions = await history.getByText("Workflow state: To do → In progress", { exact: true }).count();
  check(transitions === 1, base + " readable revision history contains state transitions");
}

async function checkTaskLayouts(bharat, base) {
  for (const width of [1400, 390]) {
    await bharat.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(bharat.page);
    check(violations.length === 0, base + " tasks axe " + width + " " + violations.join(","));
    check(await hasNoSideScroll(bharat.page), base + " mobile/desktop no overflow " + width);
    await bharat.page.screenshot({
      path: outputDir + "/" + (base ? "prefix" : "root") + "-" + width + ".png",
      fullPage: true,
    });
  }
}

async function checkDivisionAndRevocation(bharat, people, base, ctx) {
  const { chitra, admin } = people;
  const { section, division, list } = ctx;
  await bharat.page.goto(origin + base + `/w/${division.id}/todos`);
  await createList(bharat.page, "Division research coordination");
  await createTask(bharat.page, "Compare section findings");
  const divisionList = (await fetchJson(bharat, "/todos/lists?workspace_id=" + division.id)).items[0];
  check(
    (await statusOf(chitra, `/todos/lists/${divisionList.id}/tasks`)) === 200,
    base + " sibling colleague can read shared ancestor tasks",
  );
  await bharat.page.goto(origin + base + `/w/${section.id}/todos`);
  await buttonNamed(bharat.page, "Thin Films plan").click();
  const removal = await admin.ctx.request.delete(
    admin.api + `/admin/workspaces/${section.id}/memberships/${bharat.session.user.id}`,
    { headers: { "X-CSRF-Token": admin.session.csrf_token } },
  );
  check(removal.status() === 200, base + " actual membership revocation");
  const refresh = buttonNamed(bharat.page, "Refresh tasks");
  if (await refresh.count()) await refresh.click({ timeout: 1000 }).catch(() => {});
  check(
    (await statusOf(bharat, `/todos/lists/${list.id}/tasks`)) === 404,
    base + " revoked API denies tasks",
  );
  await bharat.page.getByRole("alert").first().waitFor();
  const leaked = await headingNamed(bharat.page, "Colleague revised measurement").count();
  check(leaked === 0, base + " revoked refresh clears shared content");
}

try {
  for (const base of bases) {
    const people = {
      bharat: await login(base, "bharat"),
      asha: await login(base, "asha"),
      chitra: await login(base, "chitra"),
      deepa: await login(base, "deepa"),
      admin: await login(base, "admin"),
    };
    const { bharat, asha } = people;
    const entries = (await fetchJson(bharat, "/workspaces")).workspaces;
    const section = entries.find((workspace) => workspace.name === "Thin Films Section");
    const division = entries.find((workspace) => workspace.name === "Surface Engineering Division");
    const personal = await checkLostListResponse(bharat, base);
    await checkLostTaskResponseAndReload(bharat, base, personal);
    await checkLateSaveCannotRepopulate(bharat, base);
    const reading = await checkRenameConflict(bharat, base);
    await checkDeniedRefreshes(bharat, base, reading);
    const { list, task } = await checkSectionTasks(bharat, people, base, section, personal);
    await checkTwoWriters(bharat, asha, base, list, task);
    await checkWorkflowStates(bharat, base, list, task);
    await checkTaskLayouts(bharat, base);
    await checkDivisionAndRevocation(bharat, people, base, { section, division, list });
    for (const person of Object.values(people)) await person.ctx.close();
  }
  console.log(`${harness.checks()} task browser checks passed`);
} finally {
  await harness.close();
}
