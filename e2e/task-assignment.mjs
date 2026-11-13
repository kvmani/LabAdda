import assert from "node:assert/strict";
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

const outputDir = process.argv[2] ?? "/tmp/labadda-assignment";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { check, login } = harness;

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const headingNamed = (scope, name) => scope.getByRole("heading", { name, exact: true });
const assigneeSelect = (page) => page.getByLabel("Assignee", { exact: true });
const stateFilter = (page) => page.getByLabel("My Tasks state", { exact: true });
const noMatchingTasks = (page) =>
  page.getByText("No personal or assigned tasks match this filter.", { exact: true });
const assignmentRoute = "**/api/v1/todos/lists/*/tasks/*/assignee";

async function createListWithTask(user, workspaceId, title) {
  const response = await user.ctx.request.post(user.api + "/todos/lists", {
    headers: user.headers,
    data: { client_id: crypto.randomUUID(), title, workspace_id: workspaceId },
  });
  assert.equal(response.status(), 201);
  const list = await response.json();
  const taskResponse = await user.ctx.request.post(user.api + `/todos/lists/${list.id}/tasks`, {
    headers: user.headers,
    data: { client_id: crypto.randomUUID(), title: title + " task" },
  });
  assert.equal(taskResponse.status(), 201);
  return { list, task: await taskResponse.json() };
}

async function assignTask(user, record, assigneeId) {
  const result = await user.ctx.request.put(
    user.api + `/todos/lists/${record.list.id}/tasks/${record.task.id}/assignee`,
    { headers: user.headers, data: { user_id: assigneeId, revision: record.task.revision } },
  );
  assert.equal(result.status(), 200);
  record.task = await result.json();
}

async function seedLists(bharat, chitra, spaces) {
  const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
  const division = spaces.find((workspace) => workspace.name === "Surface Engineering Division");
  const group = spaces.find((workspace) => workspace.kind === "group");
  const shared = await createListWithTask(bharat, section.id, "Section responsibility");
  const personal = await createListWithTask(bharat, null, "Personal notebook");
  const divisionRecord = await createListWithTask(bharat, division.id, "Division coordination");
  const team = await createListWithTask(bharat, group.id, "Reading club");
  await assignTask(bharat, divisionRecord, chitra.session.user.id);
  await assignTask(bharat, team, chitra.session.user.id);
  return { section, shared, personal, divisionRecord, team };
}

async function openSharedList(bharat, base, section, shared) {
  await bharat.page.goto(origin + base + `/w/${section.id}/todos`);
  await buttonNamed(bharat.page, shared.list.title).click();
}

async function checkEligiblePickerAndAssign(bharat, asha, base, data) {
  await openSharedList(bharat, base, data.section, data.shared);
  await buttonNamed(bharat.page, "Change assignee").click();
  await assigneeSelect(bharat.page).waitFor();
  const options = await assigneeSelect(bharat.page).locator("option").allTextContents();
  const hasAsha = options.some((text) => text.includes("Asha"));
  const hasExcluded = options.some((text) => /Chitra|Deepa|Administrator|Farhan/.test(text));
  check(
    options.length === 3 && hasAsha && !hasExcluded,
    base + " eligible picker excludes siblings/parent/admin/inactive",
  );
  await assigneeSelect(bharat.page).selectOption(asha.session.user.id);
  await buttonNamed(bharat.page, "Save assignment").click();
  await bharat.page.getByText("Assignee: Asha Rao", { exact: true }).waitFor();
  check(true, base + " shared assignment persists in task view");
}

async function checkMyTasksVisibility({ bharat, asha, chitra, deepa, admin }, base, data) {
  await asha.page.goto(origin + base + "/my-tasks");
  await headingNamed(asha.page, data.shared.task.title).waitFor();
  check(true, base + " assigned colleague sees My Tasks");
  await bharat.page.goto(origin + base + "/my-tasks");
  await headingNamed(bharat.page, data.personal.task.title).waitFor();
  const sharedCount = await headingNamed(bharat.page, data.shared.task.title).count();
  check(sharedCount === 0, base + " author is not implicitly assigned shared task");
  for (const outsider of [deepa, admin]) {
    await outsider.page.goto(origin + base + "/my-tasks");
    await noMatchingTasks(outsider.page).waitFor();
    check(true, base + " parent/admin My Tasks cannot reveal section tasks");
  }
  await chitra.page.goto(origin + base + "/my-tasks");
  await headingNamed(chitra.page, data.team.task.title).waitFor();
  const divisionCount = await headingNamed(chitra.page, data.divisionRecord.task.title).count();
  check(divisionCount === 1, base + " group and ancestor assignments coexist");
}

async function checkCompletionKeepsAssignment(asha, base, data) {
  const page = asha.page;
  await page.getByRole("link", { name: "Open list: " + data.shared.list.title, exact: true }).click();
  await buttonNamed(page, data.shared.list.title).click();
  await buttonNamed(page, "Edit task: " + data.shared.task.title).click();
  await page.getByLabel("Task completed", { exact: true }).check();
  await buttonNamed(page, "Save task").click();
  await headingNamed(page, "✓ " + data.shared.task.title).waitFor();
  await page.goto(origin + base + "/my-tasks");
  await stateFilter(page).selectOption("done");
  await headingNamed(page, data.shared.task.title).waitFor();
  check(true, base + " task completion preserves assignment and state filter");
}

async function checkLostAssignmentReply(bharat, base, data) {
  const page = bharat.page;
  await openSharedList(bharat, base, data.section, data.shared);
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(bharat.session.user.id);
  await loseNextResponse(page, assignmentRoute);
  await buttonNamed(page, "Save assignment").click();
  await buttonNamed(page, "Reload task assignment").waitFor();
  check(
    await buttonNamed(page, "Save assignment").isDisabled(),
    base + " unknown assignment outcome blocks blind retry",
  );
  await buttonNamed(page, "Reload task assignment").click();
  await page.getByText("Assignee: Bharat Kulkarni", { exact: true }).waitFor();
  check(true, base + " committed lost reply resolves through task reload");
}

async function checkAssignmentConflict(bharat, asha, base, data) {
  const page = bharat.page;
  const { list, task } = data.shared;
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(asha.session.user.id);
  const taskPath = `/todos/lists/${list.id}/tasks/${task.id}`;
  const current = await (await bharat.ctx.request.get(bharat.api + taskPath)).json();
  const { description, due_date, priority, checklist, done, status, revision } = current;
  const changed = await asha.ctx.request.put(asha.api + taskPath, {
    headers: asha.headers,
    data: {
      title: "Colleague updated responsibility",
      description,
      due_date,
      priority,
      checklist,
      done,
      status,
      revision,
    },
  });
  check(changed.status() === 200, base + " concurrent task writer commits");
  await buttonNamed(page, "Save assignment").click();
  await buttonNamed(page, "Reload task assignment").waitFor();
  check(
    (await assigneeSelect(page).inputValue()) === asha.session.user.id,
    base + " assignment conflict keeps chosen colleague",
  );
  await buttonNamed(page, "Reload task assignment").click();
  await headingNamed(page, "✓ Colleague updated responsibility").waitFor();
  check(true, base + " conflict reload preserves committed task and assignment");
}

async function checkRevokedSharedTask({ bharat, admin }, base, data) {
  const page = bharat.page;
  await page.goto(origin + base + "/my-tasks");
  await headingNamed(page, "Colleague updated responsibility").waitFor();
  const removed = await admin.ctx.request.delete(
    admin.api + `/admin/workspaces/${data.section.id}/memberships/${bharat.session.user.id}`,
    { headers: admin.headers },
  );
  check(removed.status() === 200, base + " actual section membership removed");
  await buttonNamed(page, "Refresh My Tasks").click();
  await headingNamed(page, data.personal.task.title).waitFor();
  const revokedCount = await headingNamed(page, "Colleague updated responsibility").count();
  check(revokedCount === 0, base + " revoked shared task hidden while personal remains");
}

async function checkDelayedResponseCannotOverrideFilter(bharat, base, data) {
  const page = bharat.page;
  const heldList = await holdFirstResponse(page, "**/api/v1/todos/mine");
  await buttonNamed(page, "Refresh My Tasks").click();
  await heldList.captured;
  await stateFilter(page).selectOption("done");
  await noMatchingTasks(page).waitFor();
  const finished = page.waitForResponse((response) => response.url().endsWith("/todos/mine"));
  heldList.release();
  await finished;
  await nextPaint(page);
  const personalCount = await headingNamed(page, data.personal.task.title).count();
  check(personalCount === 0, base + " delayed dashboard response cannot override new filter");
  await stateFilter(page).selectOption("");
  await headingNamed(page, data.personal.task.title).waitFor();
}

async function checkMyTasksLayouts(bharat, base) {
  for (const width of [1400, 390]) {
    await bharat.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(bharat.page);
    check(violations.length === 0, base + " My Tasks axe " + width + " " + violations.join(","));
    check(await hasNoSideScroll(bharat.page), base + " My Tasks overflow " + width);
    await bharat.page.screenshot({
      path: outputDir + "/" + (base ? "prefix" : "root") + "-my-tasks-" + width + ".png",
      fullPage: true,
    });
  }
}

async function checkPersonalPickerAndUnknownWrite(bharat, base, data) {
  const page = bharat.page;
  await page.goto(origin + base + "/todos");
  await buttonNamed(page, data.personal.list.title).click();
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).waitFor();
  const options = await assigneeSelect(page).locator("option").allTextContents();
  check(options.length === 2, base + " personal picker contains only owner and unassigned");
  const pickerViolations = await axeViolations(page);
  check(pickerViolations.length === 0, base + " mobile assignment picker axe " + pickerViolations.join(","));
  check(await hasNoSideScroll(page), base + " mobile assignment picker no overflow");
  await assigneeSelect(page).selectOption(bharat.session.user.id);
  await page.route(assignmentRoute, (route) => route.abort(), { times: 1 });
  await buttonNamed(page, "Save assignment").click();
  await buttonNamed(page, "Reload task assignment").click();
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(bharat.session.user.id);
  check(
    await buttonNamed(page, "Save assignment").isEnabled(),
    base + " reload recovers unknown write even when revision did not change",
  );
  await buttonNamed(page, "Save assignment").click();
  await page.getByText("Assignee: Bharat Kulkarni", { exact: true }).waitFor();
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
    const { bharat, asha, chitra } = people;
    const spaces = (await (await bharat.ctx.request.get(bharat.api + "/workspaces")).json()).workspaces;
    const data = await seedLists(bharat, chitra, spaces);
    await checkEligiblePickerAndAssign(bharat, asha, base, data);
    await checkMyTasksVisibility(people, base, data);
    await checkCompletionKeepsAssignment(asha, base, data);
    await checkLostAssignmentReply(bharat, base, data);
    await checkAssignmentConflict(bharat, asha, base, data);
    await checkRevokedSharedTask(people, base, data);
    await checkDelayedResponseCannotOverrideFilter(bharat, base, data);
    await checkMyTasksLayouts(bharat, base);
    await checkPersonalPickerAndUnknownWrite(bharat, base, data);
    for (const person of Object.values(people)) await person.ctx.close();
  }
  console.log(`${harness.checks()} assignment browser checks passed`);
} finally {
  await harness.close();
}
