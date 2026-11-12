import {
  axeViolations,
  bases,
  call,
  hasNoSideScroll,
  holdFirstResponse,
  nextPaint,
  origin,
  startHarness,
} from "./lib/harness.mjs";

const harness = await startHarness();
const { check, login } = harness;

const linkNamed = (page, name) => page.getByRole("link", { name, exact: true });
const refreshButton = (page) => page.getByRole("button", { name: "Refresh My day", exact: true });
const noActiveTasks = (page) => page.getByText("No active tasks in this loaded view.", { exact: true });

async function createTask(user, workspaceId, title, dueDate) {
  const list = await call(user, "/todos/lists", {
    title: title + " list",
    workspace_id: workspaceId,
    client_id: crypto.randomUUID(),
  });
  const task = await call(user, `/todos/lists/${list.id}/tasks`, {
    title,
    due_date: dueDate,
    client_id: crypto.randomUUID(),
  });
  return { list, task };
}

async function seedDailyWork({ ben, asha, workspaceId, today }) {
  await createTask(ben, null, "Private daily action", today);
  const shared = await createTask(asha, workspaceId, "Shared daily action", today);
  await call(
    asha,
    `/todos/lists/${shared.list.id}/tasks/${shared.task.id}/assignee`,
    { revision: 1, user_id: ben.session.user.id },
    "PUT",
  );
  await call(ben, "/notes", {
    title: "Private daily reminder",
    body: "Check uncertainty before publication",
    due_at: new Date(Date.now() + 86400000).toISOString(),
  });
  await call(asha, `/workspaces/${workspaceId}/chat`, {
    body: "@ben examine the witness blank",
    client_id: crypto.randomUUID(),
  });
}

async function checkOverviewContent(ben, base, today) {
  const page = ben.page;
  await page.goto(origin + base + "/today");
  await linkNamed(page, "Private daily action").waitFor();
  await linkNamed(page, "Shared daily action").waitFor();
  check(
    await linkNamed(page, "Private daily reminder").isVisible(),
    base + " daily overview combines personal work assigned tasks and private reminders",
  );
  const dueToday = await page.getByText("Due today " + today, { exact: false }).count();
  check(dueToday === 2, base + " date-only task deadlines use advertised calendar date");
  await page.getByRole("button", { name: /mention: @ben examine/ }).waitFor();
  const unreadRegion = page.getByRole("region", { name: "Unread conversations", exact: true });
  check(
    await unreadRegion.getByText("1 unread", { exact: false }).isVisible(),
    base + " current mentions and unread source are shown",
  );
}

async function checkOverviewLayouts(ben, base) {
  for (const width of [1400, 390]) {
    await ben.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(ben.page);
    check(!violations.length, base + " daily overview accessibility " + width + " " + violations);
    check(await hasNoSideScroll(ben.page), base + " daily overview overflow " + width);
  }
}

async function checkSiblingOverview(chen, base) {
  await chen.page.goto(origin + base + "/today");
  await noActiveTasks(chen.page).waitFor();
  const privateReminder = await chen.page.getByText("Private daily reminder", { exact: true }).count();
  const sharedAction = await chen.page.getByText("Shared daily action", { exact: true }).count();
  check(
    privateReminder === 0 && sharedAction === 0,
    base + " sibling overview cannot expose private or unassigned section work",
  );
}

async function checkReadFailureIsNotZero(ben, base) {
  const page = ben.page;
  await page.route("**/api/v1/dashboard", (route) => route.abort(), { times: 1 });
  await refreshButton(page).click();
  await page.getByRole("alert").waitFor();
  check(
    (await noActiveTasks(page).count()) === 0,
    base + " overview read failure is unavailable rather than a false zero",
  );
  await refreshButton(page).click();
  await linkNamed(page, "Shared daily action").waitFor();
}

async function checkDelayedResponseAfterRevocation(ben, admin, base, workspaceId) {
  const page = ben.page;
  const heldOverview = await holdFirstResponse(page, "**/api/v1/dashboard");
  await refreshButton(page).click();
  await heldOverview.captured;
  const delivered = page.waitForResponse((response) => response.request() === heldOverview.request());
  await call(
    admin,
    `/admin/workspaces/${workspaceId}/memberships/${ben.session.user.id}`,
    undefined,
    "DELETE",
  );
  await linkNamed(page, "Private daily action").waitFor();
  await page.evaluate(() => {
    window.__dailyLeaked = false;
    new MutationObserver(() => {
      if (document.body.innerText.includes("Shared daily action")) window.__dailyLeaked = true;
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  heldOverview.release();
  await (await delivered).finished();
  await nextPaint(page);
  const leaked = await page.evaluate(() => window.__dailyLeaked);
  const sharedShown = await page.getByText("Shared daily action", { exact: true }).count();
  check(!leaked && sharedShown === 0, base + " delayed daily response cannot restore revoked source");
  check(
    await linkNamed(page, "Private daily action").isVisible(),
    base + " personal work survives source grant loss",
  );
}

try {
  for (const base of bases) {
    const ben = await login(base, "ben");
    const asha = await login(base, "asha");
    const chen = await login(base, "chen");
    const admin = await login(base, "admin");
    const workspaces = (await call(ben, "/workspaces")).workspaces;
    const workspaceId = workspaces.find((workspace) => workspace.name === "Thin Films Section").id;
    const today = (await call(ben, "/dashboard")).today;
    await seedDailyWork({ ben, asha, workspaceId, today });
    await checkOverviewContent(ben, base, today);
    await checkOverviewLayouts(ben, base);
    await checkSiblingOverview(chen, base);
    await checkReadFailureIsNotZero(ben, base);
    await checkDelayedResponseAfterRevocation(ben, admin, base, workspaceId);
    check(!ben.errors.length && !chen.errors.length, base + " no browser exceptions");
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} dashboard browser checks passed`);
} finally {
  await harness.close();
}
