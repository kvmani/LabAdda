// C3 conversion: disposable proxy fixtures only. Revokes Bharat's source grant last.
import assert from "node:assert/strict";
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

const savedNotice = "Task saved. Its source link still requires access to the original conversation.";
const sourceUnavailable = "Source unavailable or no longer accessible.";
const original =
  "Review vacancy controls α\n<script>window.fixtureExecuted=true</script> is inert research text.";

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const labelled = (scope, label) => scope.getByLabel(label, { exact: true });
const saveButton = (form) => buttonNamed(form, "Save conversation task");
const statusOf = async (user, path) => (await user.ctx.request.get(user.api + path)).status();

function createList(user, workspaceId, title) {
  return call(user, "/todos/lists", { client_id: crypto.randomUUID(), title, workspace_id: workspaceId });
}

async function openPostForm(user, base, workspaceId, body) {
  await user.page.goto(origin + base + `/w/${workspaceId}/noticeboard`);
  const card = user.page.getByRole("article").filter({ has: user.page.getByText(body, { exact: true }) });
  await buttonNamed(card, "Create task").click();
  return user.page.getByRole("form", { name: "Create task from conversation", exact: true });
}

async function openTaskList(user, base, workspaceId, list) {
  await user.page.goto(origin + base + (workspaceId ? `/w/${workspaceId}/todos` : "/todos"));
  await buttonNamed(user.page, list.title).click();
}

async function checkPrivateConversion(bharat, chitra, base, section, lists) {
  const form = await openPostForm(bharat, base, section.id, original);
  check(
    (await labelled(form, "Task description").inputValue()) === original,
    base + " post text starts an editable reviewed copy",
  );
  await labelled(form, "Task destination").selectOption("personal");
  await labelled(form, "Destination list").selectOption(lists.private.id);
  await checkLayouts(bharat, base, "conversion form");
  await labelled(form, "Task title").fill("Private control check");
  await labelled(form, "Task description").fill("Only my reviewed followup.");
  await loseNextResponse(bharat.page, "**/api/v1/todos/lists/*/from-conversation");
  await saveButton(form).click();
  await buttonNamed(form, "Retry same task copy").waitFor();
  check(
    (await labelled(form, "Task destination").isDisabled()) &&
      (await labelled(form, "Task title").isDisabled()),
    base + " lost reply freezes original text and audience",
  );
  await buttonNamed(form, "Retry same task copy").click();
  await bharat.page.getByText(savedNotice, { exact: true }).waitFor();
  const personal = (await call(bharat, `/todos/lists/${lists.private.id}/tasks`)).items;
  check(
    personal.length === 1 &&
      personal[0].description === "Only my reviewed followup." &&
      personal[0].has_source,
    base + " retry creates exactly one reviewed task and reference",
  );
  await openTaskList(bharat, base, null, lists.private);
  await buttonNamed(bharat.page, "View source reference").click();
  await bharat.page
    .getByRole("region", { name: "Task source reference" })
    .getByText(original, { exact: true })
    .waitFor();
  await checkLayouts(bharat, base, "protected source view");
  const executed = await bharat.page.locator("script").filter({ hasText: "window.fixtureExecuted" }).count();
  check(executed === 0, base + " source text is rendered without HTML execution");
  const sourceUrl = `/todos/lists/${lists.private.id}/tasks/${personal[0].id}/source`;
  check((await statusOf(chitra, sourceUrl)) === 404, base + " personal reference is owner-only");
}

async function checkSameWorkspaceConversion(bharat, base, section, lists) {
  // Same-source shared task needs no broader-audience checkbox.
  const form = await openPostForm(bharat, base, section.id, original);
  await labelled(form, "Destination list").selectOption(lists.shared.id);
  await labelled(form, "Task title").fill("Section control check");
  check(
    (await form.getByRole("checkbox").count()) === 0,
    base + " same workspace audience is shown without a broader-copy confirmation",
  );
  await saveButton(form).click();
  await bharat.page.getByText(savedNotice, { exact: true }).waitFor();
}

async function checkDivisionConversion(bharat, chitra, base, ctx) {
  // Chat-to-division requires an explicit audience choice and confirmation.
  const { section, division, lists, chatText } = ctx;
  await call(bharat, `/workspaces/${section.id}/chat`, { body: chatText, client_id: crypto.randomUUID() });
  await bharat.page.goto(origin + base + `/w/${section.id}/chat`);
  await bharat.page
    .getByRole("listitem")
    .filter({ has: bharat.page.getByText(chatText, { exact: true }) })
    .getByRole("button", { name: "Create task", exact: true })
    .click();
  const form = bharat.page.getByRole("form", { name: "Create task from conversation", exact: true });
  await labelled(form, "Task destination").selectOption(division.id);
  await labelled(form, "Destination list").selectOption(lists.division.id);
  check(await saveButton(form).isDisabled(), base + " different audience cannot save without confirmation");
  await form.getByRole("checkbox").check();
  await labelled(form, "Task destination").selectOption("personal");
  await labelled(form, "Task destination").selectOption(division.id);
  await labelled(form, "Destination list").selectOption(lists.division.id);
  check(
    !(await form.getByRole("checkbox").isChecked()),
    base + " changing destination resets audience confirmation",
  );
  await form.getByRole("checkbox").check();
  await labelled(form, "Task title").fill("Reviewed division control action");
  await labelled(form, "Task description").fill("Reviewed controls for the common division.");
  await saveButton(form).click();
  await bharat.page.getByText(savedNotice, { exact: true }).waitFor();
  const converted = (await call(bharat, `/todos/lists/${lists.division.id}/tasks`)).items[0];
  const sourcePath = `/todos/lists/${lists.division.id}/tasks/${converted.id}/source`;
  await openTaskList(chitra, base, division.id, lists.division);
  await buttonNamed(chitra.page, "View source reference").click();
  await chitra.page.getByText(sourceUnavailable, { exact: true }).waitFor();
  const reviewedVisible = await chitra.page
    .getByText("Reviewed controls for the common division.", { exact: true })
    .isVisible();
  const bodyCount = await chitra.page.getByText(chatText, { exact: true }).count();
  check(
    reviewedVisible && bodyCount === 0,
    base + " sibling sees reviewed division task without protected source body",
  );
  check(
    (await statusOf(chitra, sourcePath)) === 404,
    base + " direct source lookup does not grant sibling access",
  );
  return sourcePath;
}

async function checkPagingClearsChoice(bharat, base, section) {
  // Real pagination must not submit a previous page's hidden selected list.
  for (let index = 0; index < 25; index++) await createList(bharat, null, "Private paged " + index);
  const form = await openPostForm(bharat, base, section.id, original);
  await labelled(form, "Task destination").selectOption("personal");
  await labelled(form, "Destination list").selectOption({ index: 1 });
  await buttonNamed(form, "More destination lists").click();
  check(
    (await labelled(form, "Destination list").inputValue()) === "" && (await saveButton(form).isDisabled()),
    base + " list paging clears hidden destination choice",
  );
}

async function checkSourceOnlyRevocation(bharat, admin, base, ctx, sourcePath) {
  // Hold a successful first source lookup, revoke only source access, then release.
  const { section, division, lists, chatText } = ctx;
  const page = bharat.page;
  await openTaskList(bharat, base, division.id, lists.division);
  const heldSource = await holdFirstResponse(page, "**/api/v1" + sourcePath);
  await buttonNamed(page, "View source reference").click();
  await heldSource.captured;
  // Retain division read authority while removing the child-section source grant.
  await call(
    admin,
    `/admin/workspaces/${division.id}/memberships`,
    { user_id: bharat.session.user.id, role: "member" },
    "PUT",
  );
  const removal = await admin.ctx.request.delete(
    admin.api + `/admin/workspaces/${section.id}/memberships/${bharat.session.user.id}`,
    { headers: admin.headers },
  );
  assert.equal(removal.status(), 200);
  await page.getByText(sourceUnavailable, { exact: true }).waitFor();
  await page.evaluate((text) => {
    window.__sourceLeaked = false;
    new MutationObserver(() => {
      if (document.body.innerText.includes(text)) window.__sourceLeaked = true;
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }, chatText);
  const delivered = page.waitForResponse((response) => response.url().endsWith(sourcePath));
  heldSource.release();
  await (await delivered).finished();
  await nextPaint(page);
  await buttonNamed(page, "View source reference").waitFor();
  const leaked = await page.evaluate(() => window.__sourceLeaked);
  const textCount = await page.getByText(chatText, { exact: true }).count();
  check(
    !leaked && textCount === 0,
    base + " delayed source response cannot restore text after source-only revocation",
  );
  const remaining = (await call(bharat, `/todos/lists/${lists.division.id}/tasks`)).items;
  check(remaining.length === 1, base + " reviewed destination task survives source revocation");
}

async function saveFailureScreenshots() {
  for (const [index, context] of harness.browser.contexts().entries()) {
    for (const page of context.pages()) {
      await page.screenshot({ path: `/tmp/c3-failure-${index}.png`, fullPage: true });
      console.error((await page.locator("main").innerText()).slice(-5000));
    }
  }
}

try {
  for (const base of bases) {
    const bharat = await login(base, "bharat");
    const chitra = await login(base, "chitra");
    const admin = await login(base, "admin");
    const spaces = (await call(bharat, "/workspaces")).workspaces;
    const section = spaces.find((workspace) => workspace.name === "Thin Films Section");
    const division = spaces.find((workspace) => workspace.name === "Surface Engineering Division");
    const lists = {
      private: await createList(bharat, null, "Personal followups"),
      shared: await createList(bharat, section.id, "Section actions"),
      division: await createList(bharat, division.id, "Division actions"),
    };
    await call(bharat, `/workspaces/${section.id}/posts`, { body: original, client_id: crypto.randomUUID() });
    const ctx = {
      section,
      division,
      lists,
      chatText: "Repeat three GC controls before the division review.",
    };
    await checkPrivateConversion(bharat, chitra, base, section, lists);
    await checkSameWorkspaceConversion(bharat, base, section, lists);
    const sourcePath = await checkDivisionConversion(bharat, chitra, base, ctx);
    await checkPagingClearsChoice(bharat, base, section);
    await checkSourceOnlyRevocation(bharat, admin, base, ctx, sourcePath);
    check(bharat.errors.length === 0 && chitra.errors.length === 0, base + " no browser exceptions");
    await Promise.all([bharat.ctx.close(), chitra.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} conversion browser checks passed`);
} catch (error) {
  await saveFailureScreenshots();
  throw error;
} finally {
  await harness.close();
}
