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

const outputDir = process.argv[2] ?? "/tmp/labadda-task-comments";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { check, login } = harness;

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const commentBox = (scope) => scope.getByLabel("New task comment", { exact: true });
const commentItem = (region, text) => region.getByRole("listitem").getByText(text, { exact: true });
const statusOf = async (user, path) => (await user.ctx.request.get(user.api + path)).status();
const jsonOf = async (user, path) => (await user.ctx.request.get(user.api + path)).json();

async function createListWithTask(user, workspaceId, title) {
  const listResponse = await user.ctx.request.post(user.api + "/todos/lists", {
    headers: user.headers,
    data: { client_id: crypto.randomUUID(), title, workspace_id: workspaceId },
  });
  const list = await listResponse.json();
  const taskResponse = await user.ctx.request.post(user.api + `/todos/lists/${list.id}/tasks`, {
    headers: user.headers,
    data: { client_id: crypto.randomUUID(), title: title + " task" },
  });
  const task = await taskResponse.json();
  return { list, task, path: `/todos/lists/${list.id}/tasks/${task.id}/comments` };
}

async function openComments(user, base, workspaceId, record) {
  await user.page.goto(origin + base + (workspaceId ? `/w/${workspaceId}/todos` : "/todos"));
  await buttonNamed(user.page, record.list.title).click();
  await buttonNamed(user.page, "View comments").click();
  const region = user.page.getByRole("region", { name: "Task comments", exact: true });
  await buttonNamed(region, "Refresh comments").waitFor();
  return region;
}

async function postComment(region, text) {
  await commentBox(region).fill(text);
  await buttonNamed(region, "Post comment").click();
  await commentItem(region, text).waitFor();
}

async function seedTasks(bharat, section, division) {
  return {
    shared: await createListWithTask(bharat, section.id, "Research discussion"),
    personal: await createListWithTask(bharat, null, "Private followup"),
    other: await createListWithTask(bharat, null, "Other private research"),
    divisionTask: await createListWithTask(bharat, division.id, "Division analysis"),
  };
}

async function checkLostCommentReply(bharat, base, region, shared, text) {
  await commentBox(region).fill(text);
  await loseNextResponse(bharat.page, "**/api/v1/todos/lists/*/tasks/*/comments");
  await buttonNamed(region, "Post comment").click();
  await buttonNamed(region, "Retry same comment").waitFor();
  check(await commentBox(region).isDisabled(), base + " unknown comment freezes original intent");
  await buttonNamed(region, "Retry same comment").click();
  await commentItem(region, text).waitFor();
  const committed = (await jsonOf(bharat, shared.path)).items;
  check(
    committed.length === 1 && committed[0].sequence === 1,
    base + " lost reply recovers exactly one comment",
  );
  check((await region.locator("script").count()) === 0, base + " active-looking text is escaped");
  const task = await jsonOf(bharat, shared.path.replace("/comments", ""));
  check(task.revision === 1, base + " comment does not change task revision");
}

async function checkColleagueDiscussion(bharat, asha, base, region, data, text) {
  const ashaRegion = await openComments(asha, base, data.section.id, data.shared);
  await ashaRegion.getByText(text, { exact: true }).waitFor();
  await postComment(ashaRegion, "Instrument calibrated before this run.");
  await buttonNamed(region, "Refresh comments").click();
  await region.getByText("Instrument calibrated before this run.", { exact: true }).waitFor();
  const authorCount = await region.getByText("Asha Rao", { exact: true }).count();
  check(authorCount === 1, base + " colleague authorship and discussion visible after refresh");
}

async function checkDraftSurvivesRefreshAndEdit(bharat, base, region, shared) {
  const page = bharat.page;
  const draft = "Unsent research followup β";
  await commentBox(region).fill(draft);
  const refreshed = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      response.url().endsWith(`/todos/lists/${shared.list.id}/tasks`),
  );
  await buttonNamed(page, "Refresh tasks").click();
  await refreshed;
  await nextPaint(page);
  check((await commentBox(region).inputValue()) === draft, base + " draft survives same-list refresh");
  await buttonNamed(page, "Edit task: " + shared.task.title).click();
  await page.getByLabel("Priority", { exact: true }).selectOption("high");
  await buttonNamed(page, "Save task").click();
  await page.getByText("To do · high priority", { exact: true }).waitFor();
  check((await commentBox(region).inputValue()) === draft, base + " draft survives task field edit");
  await buttonNamed(region, "Post comment").click();
  await region.getByText(draft, { exact: true }).waitFor();
  return draft;
}

async function checkAudienceBoundaries({ bharat, asha, chitra, deepa, admin }, base, data) {
  for (const outsider of [chitra, deepa, admin]) {
    check(
      (await statusOf(outsider, data.shared.path)) === 404,
      base + " sibling/parent/admin cannot read section discussion",
    );
  }
  const divisionRegion = await openComments(chitra, base, data.division.id, data.divisionTask);
  await postComment(divisionRegion, "Cross-section correlation is ready for division review.");
  const divisionComments = await jsonOf(deepa, data.divisionTask.path);
  check(
    divisionComments.items[0].author.id === chitra.session.user.id,
    base + " division discussion spans sibling sections and steward",
  );
  const privateRegion = await openComments(bharat, base, null, data.personal);
  await postComment(privateRegion, "Owner-only experimental note.");
  for (const outsider of [asha, chitra, deepa, admin]) {
    check(
      (await statusOf(outsider, data.personal.path)) === 404,
      base + " personal discussion denies all colleagues/admin",
    );
  }
  return privateRegion;
}

async function checkDelayedCommentsOnOtherTask(bharat, base, privateRegion, data) {
  const page = bharat.page;
  const heldComments = await holdFirstResponse(page, "**/api/v1" + data.personal.path);
  await buttonNamed(privateRegion, "Refresh comments").click();
  await heldComments.captured;
  await buttonNamed(page, data.other.list.title).click();
  await page.getByRole("heading", { name: data.other.task.title, exact: true }).waitFor();
  const finished = page.waitForResponse((response) => response.url().endsWith(data.personal.path));
  heldComments.release();
  await finished;
  await nextPaint(page);
  const leaked = await page.getByText("Owner-only experimental note.", { exact: true }).count();
  const regions = await page.getByRole("region", { name: "Task comments", exact: true }).count();
  check(leaked === 0 && regions === 0, base + " delayed comments cannot populate another task");
}

async function checkReadOnlyWorkspace({ bharat, asha }, base, data, draft) {
  const policy = await asha.ctx.request.patch(asha.api + "/workspaces/" + data.section.id + "/policy", {
    headers: asha.headers,
    data: { posting_policy: "read_only" },
  });
  check(policy.status() === 200, base + " real workspace read-only policy applied");
  const region = await openComments(bharat, base, data.section.id, data.shared);
  await region.getByText(draft, { exact: true }).waitFor();
  const postButtons = await buttonNamed(region, "Post comment").count();
  check(postButtons === 0, base + " read-only view hides posting controls");
  const denied = await bharat.ctx.request.post(bharat.api + data.shared.path, {
    headers: bharat.headers,
    data: { client_id: crypto.randomUUID(), body: "Denied" },
  });
  check(denied.status() === 403, base + " read-only direct posting denied");
}

async function checkCommentLayouts(bharat, base) {
  for (const width of [1400, 390]) {
    await bharat.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(bharat.page);
    check(violations.length === 0, base + " comments axe " + width + " " + violations.join(","));
    check(await hasNoSideScroll(bharat.page), base + " comments overflow " + width);
    await bharat.page.screenshot({
      path: outputDir + "/" + (base ? "prefix" : "root") + "-" + width + ".png",
      fullPage: true,
    });
  }
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
    const { bharat, asha, admin } = people;
    const spaces = (await jsonOf(bharat, "/workspaces")).workspaces;
    const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
    const division = spaces.find((workspace) => workspace.name === "Surface Engineering Division");
    const tasks = await seedTasks(bharat, section, division);
    const data = { section, division, ...tasks };
    const region = await openComments(bharat, base, section.id, data.shared);
    await region.getByText("No comments yet.", { exact: true }).waitFor();
    const text = 'Calibrate α first.\n<script>alert("inert fixture")</script> is plain text.';
    await checkLostCommentReply(bharat, base, region, data.shared, text);
    await checkColleagueDiscussion(bharat, asha, base, region, data, text);
    const draft = await checkDraftSurvivesRefreshAndEdit(bharat, base, region, data.shared);
    const privateRegion = await checkAudienceBoundaries(people, base, data);
    await checkDelayedCommentsOnOtherTask(bharat, base, privateRegion, data);
    await checkReadOnlyWorkspace(people, base, data, draft);
    await checkCommentLayouts(bharat, base);
    await admin.ctx.request.delete(
      admin.api + `/admin/workspaces/${section.id}/memberships/${bharat.session.user.id}`,
      { headers: admin.headers },
    );
    check((await statusOf(bharat, data.shared.path)) === 404, base + " revoked discussion access denied");
    for (const person of Object.values(people)) await person.ctx.close();
  }
  console.log(`${harness.checks()} comment browser checks passed`);
} finally {
  await harness.close();
}
