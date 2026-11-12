import { mkdirSync } from "node:fs";
import {
  axeViolations,
  bases,
  call,
  hasNoSideScroll,
  loseNextResponse,
  origin,
  startHarness,
} from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/c5-preferences";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness({ timezoneId: "Asia/Kolkata" });
const { check, login } = harness;

const labelled = (scope, label) => scope.getByLabel(label, { exact: true });
const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const reloadButton = (page) => buttonNamed(page, "Reload current preferences (replaces draft)");
const saveButton = (page) => buttonNamed(page, "Save alert preferences");
const mentionsBox = (page) => labelled(page, "Mentions in posts and chat");
const remindersBox = (page) => labelled(page, "Scheduled note and post reminders");
const noticesBox = (page) => labelled(page, "Official notice alerts");
const switcher = (page) => labelled(page, "Switch workspace");

function screenshot(page, base, suffix) {
  return page.screenshot({ path: outputDir + "/" + (base ? "prefix" : "root") + suffix, fullPage: true });
}

async function openPreferences(page, base) {
  await page.goto(origin + base + "/preferences");
  await page.getByText("Current alert choices loaded.", { exact: true }).waitFor();
}

async function checkUncertainSaveAndRecovery(ben, base) {
  const page = ben.page;
  await openPreferences(page, base);
  check(await mentionsBox(page).isChecked(), base + " compatible alert defaults are enabled");
  await mentionsBox(page).uncheck();
  await remindersBox(page).uncheck();
  await loseNextResponse(page, "**/api/v1/notification-preferences", { onlyPut: true });
  await saveButton(page).click();
  await reloadButton(page).waitFor();
  check(await saveButton(page).isDisabled(), base + " uncertain preference save blocks blind repeat");
  await reloadButton(page).click();
  await buttonNamed(page, "Refresh alert preferences").waitFor();
  check(!(await mentionsBox(page).isChecked()), base + " explicit reload recovers committed alert choices");
}

async function checkMutedCategoryAndIndependence(ben, chen, base, mention) {
  await mention("While muted");
  const notifications = await call(ben, "/notifications");
  check(
    notifications.items.length === 1,
    base + " muted category creates no new alert and retains prior history",
  );
  await openPreferences(chen.page, base);
  check(await mentionsBox(chen.page).isChecked(), base + " colleague preferences remain independent");
  await screenshot(ben.page, base, "-alert-preferences.png");
}

async function checkConcurrentConflict(ben, base) {
  const second = await ben.ctx.newPage();
  await openPreferences(second, base);
  await noticesBox(second).uncheck();
  await mentionsBox(ben.page).check();
  await remindersBox(ben.page).check();
  await saveButton(ben.page).click();
  await ben.page.getByText("Alert preferences saved.", { exact: true }).waitFor();
  await saveButton(second).click();
  await reloadButton(second).waitFor();
  check(
    !(await noticesBox(second).isChecked()),
    base + " concurrent settings conflict retains draft instead of overwriting",
  );
  await reloadButton(second).click();
  await buttonNamed(second, "Refresh alert preferences").waitFor();
  check(await noticesBox(second).isChecked(), base + " explicit conflict reload shows latest owner choices");
  await second.close();
}

async function checkLayouts(ben, base) {
  for (const width of [1400, 390]) {
    await ben.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(ben.page);
    check(!violations.length, base + " preferences accessibility " + width + " " + violations);
    check(await hasNoSideScroll(ben.page), base + " preferences overflow " + width);
  }
}

async function checkMobileMenu(ben, base) {
  const page = ben.page;
  await switcher(page).selectOption("today");
  await page.getByRole("heading", { name: "My day", exact: true }).waitFor();
  check((await switcher(page).inputValue()) === "today", base + " mobile menu selects daily overview");
  await switcher(page).selectOption("private_conversation");
  await page.getByRole("heading", { name: "Start a private conversation", exact: true }).waitFor();
  check(
    (await switcher(page).inputValue()) === "private_conversation",
    base + " mobile menu exposes private conversation creation",
  );
}

async function seedDailyWork(ben, asha, workspaceId) {
  const today = (await call(ben, "/dashboard")).today;
  const personal = await call(ben, "/todos/lists", {
    title: "Daily calibration notes",
    client_id: crypto.randomUUID(),
  });
  await call(ben, `/todos/lists/${personal.id}/tasks`, {
    title: "Inspect 40 nm reference drift",
    due_date: today,
    priority: "high",
    client_id: crypto.randomUUID(),
  });
  const shared = await call(asha, "/todos/lists", {
    title: "Cross-check controls",
    workspace_id: workspaceId,
    client_id: crypto.randomUUID(),
  });
  const work = await call(asha, `/todos/lists/${shared.id}/tasks`, {
    title: "Resolve catalyst control uncertainty",
    due_date: today,
    client_id: crypto.randomUUID(),
  });
  await call(
    asha,
    `/todos/lists/${shared.id}/tasks/${work.id}/assignee`,
    { revision: 1, user_id: ben.session.user.id },
    "PUT",
  );
  await call(ben, "/notes", {
    title: "Before division review",
    body: "Compare blank and witness uncertainty before sharing the conclusion.",
    due_at: new Date(Date.now() + 86400000).toISOString(),
  });
}

try {
  for (const base of bases) {
    const ben = await login(base, "ben");
    const asha = await login(base, "asha");
    const chen = await login(base, "chen");
    const workspaces = (await call(ben, "/workspaces")).workspaces;
    const workspaceId = workspaces.find((row) => row.name === "Thin Films Section").id;
    const mention = (text) =>
      call(asha, `/workspaces/${workspaceId}/chat`, {
        body: "@ben " + text,
        client_id: crypto.randomUUID(),
      });
    await mention("Before muting");
    await checkUncertainSaveAndRecovery(ben, base);
    await checkMutedCategoryAndIndependence(ben, chen, base, mention);
    await checkConcurrentConflict(ben, base);
    await mention("After enabling");
    const afterEnabling = await call(ben, "/notifications");
    check(
      afterEnabling.items.length === 2,
      base + " enabling resumes new alerts without replaying skipped occurrence",
    );
    await checkLayouts(ben, base);
    await checkMobileMenu(ben, base);
    await seedDailyWork(ben, asha, workspaceId);
    await ben.page.setViewportSize({ width: 1400, height: 1100 });
    await ben.page.goto(origin + base + "/today");
    await ben.page.getByRole("link", { name: "Inspect 40 nm reference drift", exact: true }).waitFor();
    await screenshot(ben.page, base, "-my-day.png");
    check(!ben.errors.length && !chen.errors.length, base + " no browser exceptions");
    await Promise.all([ben.ctx.close(), asha.ctx.close(), chen.ctx.close()]);
  }
  console.log(`${harness.checks()} alert preference browser checks passed`);
} finally {
  await harness.close();
}
