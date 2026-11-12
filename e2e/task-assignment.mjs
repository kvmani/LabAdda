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

async function seedLists(ben, chen, spaces) {
  const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
  const division = spaces.find((workspace) => workspace.name === "Surface Science Division");
  const group = spaces.find((workspace) => workspace.kind === "group");
  const shared = await createListWithTask(ben, section.id, "Section responsibility");
  const personal = await createListWithTask(ben, null, "Personal notebook");
  const divisionRecord = await createListWithTask(ben, division.id, "Division coordination");
  const team = await createListWithTask(ben, group.id, "Reading club");
  await assignTask(ben, divisionRecord, chen.session.user.id);
  await assignTask(ben, team, chen.session.user.id);
  return { section, shared, personal, divisionRecord, team };
}

async function openSharedList(ben, base, section, shared) {
  await ben.page.goto(origin + base + `/w/${section.id}/todos`);
  await buttonNamed(ben.page, shared.list.title).click();
}

async function checkEligiblePickerAndAssign(ben, asha, base, data) {
  await openSharedList(ben, base, data.section, data.shared);
  await buttonNamed(ben.page, "Change assignee").click();
  await assigneeSelect(ben.page).waitFor();
  const options = await assigneeSelect(ben.page).locator("option").allTextContents();
  const hasAsha = options.some((text) => text.includes("Asha"));
  const hasExcluded = options.some((text) => /Chen|Dana|Administrator|Fay/.test(text));
  check(
    options.length === 3 && hasAsha && !hasExcluded,
    base + " eligible picker excludes siblings/parent/admin/inactive",
  );
  await assigneeSelect(ben.page).selectOption(asha.session.user.id);
  await buttonNamed(ben.page, "Save assignment").click();
  await ben.page.getByText("Assignee: Asha Rao", { exact: true }).waitFor();
  check(true, base + " shared assignment persists in task view");
}

async function checkMyTasksVisibility({ ben, asha, chen, dana, admin }, base, data) {
  await asha.page.goto(origin + base + "/my-tasks");
  await headingNamed(asha.page, data.shared.task.title).waitFor();
  check(true, base + " assigned colleague sees My Tasks");
  await ben.page.goto(origin + base + "/my-tasks");
  await headingNamed(ben.page, data.personal.task.title).waitFor();
  const sharedCount = await headingNamed(ben.page, data.shared.task.title).count();
  check(sharedCount === 0, base + " author is not implicitly assigned shared task");
  for (const outsider of [dana, admin]) {
    await outsider.page.goto(origin + base + "/my-tasks");
    await noMatchingTasks(outsider.page).waitFor();
    check(true, base + " parent/admin My Tasks cannot reveal section tasks");
  }
  await chen.page.goto(origin + base + "/my-tasks");
  await headingNamed(chen.page, data.team.task.title).waitFor();
  const divisionCount = await headingNamed(chen.page, data.divisionRecord.task.title).count();
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

async function checkLostAssignmentReply(ben, base, data) {
  const page = ben.page;
  await openSharedList(ben, base, data.section, data.shared);
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(ben.session.user.id);
  await loseNextResponse(page, assignmentRoute);
  await buttonNamed(page, "Save assignment").click();
  await buttonNamed(page, "Reload task assignment").waitFor();
  check(
    await buttonNamed(page, "Save assignment").isDisabled(),
    base + " unknown assignment outcome blocks blind retry",
  );
  await buttonNamed(page, "Reload task assignment").click();
  await page.getByText("Assignee: Ben Okafor", { exact: true }).waitFor();
  check(true, base + " committed lost reply resolves through task reload");
}

async function checkAssignmentConflict(ben, asha, base, data) {
  const page = ben.page;
  const { list, task } = data.shared;
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(asha.session.user.id);
  const taskPath = `/todos/lists/${list.id}/tasks/${task.id}`;
  const current = await (await ben.ctx.request.get(ben.api + taskPath)).json();
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

async function checkRevokedSharedTask({ ben, admin }, base, data) {
  const page = ben.page;
  await page.goto(origin + base + "/my-tasks");
  await headingNamed(page, "Colleague updated responsibility").waitFor();
  const removed = await admin.ctx.request.delete(
    admin.api + `/admin/workspaces/${data.section.id}/memberships/${ben.session.user.id}`,
    { headers: admin.headers },
  );
  check(removed.status() === 200, base + " actual section membership removed");
  await buttonNamed(page, "Refresh My Tasks").click();
  await headingNamed(page, data.personal.task.title).waitFor();
  const revokedCount = await headingNamed(page, "Colleague updated responsibility").count();
  check(revokedCount === 0, base + " revoked shared task hidden while personal remains");
}

async function checkDelayedResponseCannotOverrideFilter(ben, base, data) {
  const page = ben.page;
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

async function checkMyTasksLayouts(ben, base) {
  for (const width of [1400, 390]) {
    await ben.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(ben.page);
    check(violations.length === 0, base + " My Tasks axe " + width + " " + violations.join(","));
    check(await hasNoSideScroll(ben.page), base + " My Tasks overflow " + width);
    await ben.page.screenshot({
      path: outputDir + "/" + (base ? "prefix" : "root") + "-my-tasks-" + width + ".png",
      fullPage: true,
    });
  }
}

async function checkPersonalPickerAndUnknownWrite(ben, base, data) {
  const page = ben.page;
  await page.goto(origin + base + "/todos");
  await buttonNamed(page, data.personal.list.title).click();
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).waitFor();
  const options = await assigneeSelect(page).locator("option").allTextContents();
  check(options.length === 2, base + " personal picker contains only owner and unassigned");
  const pickerViolations = await axeViolations(page);
  check(pickerViolations.length === 0, base + " mobile assignment picker axe " + pickerViolations.join(","));
  check(await hasNoSideScroll(page), base + " mobile assignment picker no overflow");
  await assigneeSelect(page).selectOption(ben.session.user.id);
  await page.route(assignmentRoute, (route) => route.abort(), { times: 1 });
  await buttonNamed(page, "Save assignment").click();
  await buttonNamed(page, "Reload task assignment").click();
  await buttonNamed(page, "Change assignee").click();
  await assigneeSelect(page).selectOption(ben.session.user.id);
  check(
    await buttonNamed(page, "Save assignment").isEnabled(),
    base + " reload recovers unknown write even when revision did not change",
  );
  await buttonNamed(page, "Save assignment").click();
  await page.getByText("Assignee: Ben Okafor", { exact: true }).waitFor();
}

try {
  for (const base of bases) {
    const people = {
      ben: await login(base, "ben"),
      asha: await login(base, "asha"),
      chen: await login(base, "chen"),
      dana: await login(base, "dana"),
      admin: await login(base, "admin"),
    };
    const { ben, asha, chen } = people;
    const spaces = (await (await ben.ctx.request.get(ben.api + "/workspaces")).json()).workspaces;
    const data = await seedLists(ben, chen, spaces);
    await checkEligiblePickerAndAssign(ben, asha, base, data);
    await checkMyTasksVisibility(people, base, data);
    await checkCompletionKeepsAssignment(asha, base, data);
    await checkLostAssignmentReply(ben, base, data);
    await checkAssignmentConflict(ben, asha, base, data);
    await checkRevokedSharedTask(people, base, data);
    await checkDelayedResponseCannotOverrideFilter(ben, base, data);
    await checkMyTasksLayouts(ben, base);
    await checkPersonalPickerAndUnknownWrite(ben, base, data);
    for (const person of Object.values(people)) await person.ctx.close();
  }
  console.log(`${harness.checks()} assignment browser checks passed`);
} finally {
  await harness.close();
}
