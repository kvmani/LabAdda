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

async function seedDailyWork({ bharat, asha, workspaceId, today }) {
  await createTask(bharat, null, "Private daily action", today);
  const shared = await createTask(asha, workspaceId, "Shared daily action", today);
  await call(
    asha,
    `/todos/lists/${shared.list.id}/tasks/${shared.task.id}/assignee`,
    { revision: 1, user_id: bharat.session.user.id },
    "PUT",
  );
  await call(bharat, "/notes", {
    title: "Private daily reminder",
    body: "Check uncertainty before publication",
    due_at: new Date(Date.now() + 86400000).toISOString(),
  });
  await call(asha, `/workspaces/${workspaceId}/chat`, {
    body: "@bharat examine the witness blank",
    client_id: crypto.randomUUID(),
  });
}

async function checkOverviewContent(bharat, base, today) {
  const page = bharat.page;
  await page.goto(origin + base + "/today");
  await linkNamed(page, "Private daily action").waitFor();
  await linkNamed(page, "Shared daily action").waitFor();
  check(
    await linkNamed(page, "Private daily reminder").isVisible(),
    base + " daily overview combines personal work assigned tasks and private reminders",
  );
  const dueToday = await page.getByText("Due today " + today, { exact: false }).count();
  check(dueToday === 2, base + " date-only task deadlines use advertised calendar date");
  await page.getByRole("button", { name: /mention: @bharat examine/ }).waitFor();
  const unreadRegion = page.getByRole("region", { name: "Unread conversations", exact: true });
  check(
    await unreadRegion.getByText("1 unread", { exact: false }).isVisible(),
    base + " current mentions and unread source are shown",
  );
}

async function checkOverviewLayouts(bharat, base) {
  for (const width of [1400, 390]) {
    await bharat.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(bharat.page);
    check(!violations.length, base + " daily overview accessibility " + width + " " + violations);
    check(await hasNoSideScroll(bharat.page), base + " daily overview overflow " + width);
  }
}

async function checkSiblingOverview(chitra, base) {
  await chitra.page.goto(origin + base + "/today");
  await noActiveTasks(chitra.page).waitFor();
  const privateReminder = await chitra.page.getByText("Private daily reminder", { exact: true }).count();
  const sharedAction = await chitra.page.getByText("Shared daily action", { exact: true }).count();
  check(
    privateReminder === 0 && sharedAction === 0,
    base + " sibling overview cannot expose private or unassigned section work",
  );
}

async function checkReadFailureIsNotZero(bharat, base) {
  const page = bharat.page;
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

async function checkDelayedResponseAfterRevocation(bharat, admin, base, workspaceId) {
  const page = bharat.page;
  const heldOverview = await holdFirstResponse(page, "**/api/v1/dashboard");
  await refreshButton(page).click();
  await heldOverview.captured;
  const delivered = page.waitForResponse((response) => response.request() === heldOverview.request());
  await call(
    admin,
    `/admin/workspaces/${workspaceId}/memberships/${bharat.session.user.id}`,
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
    const bharat = await login(base, "bharat");
    const asha = await login(base, "asha");
    const chitra = await login(base, "chitra");
    const admin = await login(base, "admin");
    const workspaces = (await call(bharat, "/workspaces")).workspaces;
    const workspaceId = workspaces.find((workspace) => workspace.name === "Thin Films Section").id;
    const today = (await call(bharat, "/dashboard")).today;
    await seedDailyWork({ bharat, asha, workspaceId, today });
    await checkOverviewContent(bharat, base, today);
    await checkOverviewLayouts(bharat, base);
    await checkSiblingOverview(chitra, base);
    await checkReadFailureIsNotZero(bharat, base);
    await checkDelayedResponseAfterRevocation(bharat, admin, base, workspaceId);
    check(!bharat.errors.length && !chitra.errors.length, base + " no browser exceptions");
    await Promise.all([bharat.ctx.close(), asha.ctx.close(), chitra.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} dashboard browser checks passed`);
} finally {
  await harness.close();
}
