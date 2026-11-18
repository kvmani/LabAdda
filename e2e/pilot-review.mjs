// Fresh-review regressions: real workbench edits, manual activation, protected cockpit at root/prefix.
import { mkdirSync } from "node:fs";
import { bases, call, origin, startHarness } from "./lib/harness.mjs";

const harness = await startHarness();
const { check, login, checkLayouts } = harness;
const shots = "/tmp/labadda-pilot-review-20261117";
mkdirSync(shots, { recursive: true });

async function home(base, tag) {
  const member = await login(base, "bharat");
  const title = `Review tensile action ${tag}`;
  const list = await call(member, "/todos/lists", {
    title: "Review personal plan",
    client_id: crypto.randomUUID(),
  });
  const task = await call(member, `/todos/lists/${list.id}/tasks`, { title, client_id: crypto.randomUUID() });
  await member.page.goto(origin + base + "/");
  const complete = member.page.getByRole("button", { name: `Mark task completed: ${title}`, exact: true });
  await complete.click();
  await member.page.getByText("marked as completed!", { exact: false }).waitFor();
  check(
    (await call(member, `/todos/lists/${list.id}/tasks/${task.id}`)).status === "done",
    tag + " home completion is durable",
  );
  await member.page.getByRole("button", { name: "Undo", exact: true }).click();
  await complete.waitFor();
  check(
    (await call(member, `/todos/lists/${list.id}/tasks/${task.id}`)).status === "todo",
    tag + " undo restores prior task status",
  );
  const note = member.page.getByPlaceholder("Jot a quick note or reminder... (Press Enter)");
  await note.fill(`Review private microscopy ${tag}`);
  await member.page.getByRole("button", { name: "Add note", exact: true }).click();
  await member.page.getByRole("link", { name: `Review private microscopy ${tag}`, exact: false }).waitFor();
  check(
    (await call(member, "/notes")).notes.some((row) => row.title === `Review private microscopy ${tag}`),
    tag + " quick note persists privately",
  );
  await member.page.getByRole("button", { name: /Open keyboard shortcuts/ }).click();
  await member.page.getByRole("dialog", { name: "Keyboard Shortcuts" }).waitFor();
  await member.page.keyboard.press("Escape");
  check(
    await member.page
      .getByRole("button", { name: /Open keyboard shortcuts/ })
      .evaluate((node) => node === document.activeElement),
    tag + " shortcut dialog returns focus",
  );
  await checkLayouts(member, base, "Home");
  await member.page.screenshot({ path: `${shots}/${tag}-home.png`, fullPage: true });
  check(member.errors.length === 0, tag + " home has no JavaScript errors");
  await member.ctx.close();
}

async function applications(base, tag) {
  const admin = await login(base, "admin");
  const catalogue = await admin.ctx.request.get(admin.api + "/join-requests/units");
  const units = (await catalogue.json()).units;
  check(
    units.every((unit) => unit.kind === "org"),
    tag + " public affiliation catalogue excludes private groups and projects",
  );
  const username = "anita.review." + tag;
  // Public submit uses the anonymous endpoint; it does not activate or grant an account.
  await call(admin, "/join-requests", { full_name: "Anita Rao", username, unit_id: units[0].id });
  await admin.page.goto(origin + base + "/admin/people");
  await admin.page.getByRole("tab", { name: /Join Applications/ }).click();
  await admin.page.getByRole("heading", { name: "Anita Rao", exact: true }).waitFor();
  await admin.page.getByRole("button", { name: /Review, Verify & Approve/ }).click();
  const dialog = admin.page.getByRole("dialog", { name: "Verify & Approve Membership Application" });
  await dialog.waitFor();
  await dialog.getByLabel("Full Name (Official):").fill("Dr. Anita Rao");
  await dialog.getByRole("button", { name: /Confirm & Issue Activation Code/ }).click();
  const slip = admin.page.getByRole("dialog", { name: "Account Created & Activation Code Issued" });
  await slip.waitFor();
  check(
    await slip.getByText("Dr. Anita Rao", { exact: true }).isVisible(),
    tag + " activation slip uses verified identity",
  );
  const code = await slip.locator(".activation-modal-slip__code").textContent();
  check(Boolean(code?.length), tag + " approval returns one-time activation code after commit");
  await slip.getByRole("button", { name: "Done", exact: true }).click();
  await admin.page.getByRole("tab", { name: /Approved/ }).click();
  await admin.page.getByRole("heading", { name: "Dr. Anita Rao", exact: true }).waitFor();
  await checkLayouts(admin, base, "Join applications");
  await admin.page.screenshot({ path: `${shots}/${tag}-applications.png`, fullPage: true });
  check(admin.errors.length === 0, tag + " application review has no JavaScript errors");
  await admin.ctx.close();
}

async function cockpit(base, tag) {
  const admin = await login(base, "admin");
  await admin.page.goto(origin + base + "/admin");
  await admin.page.getByRole("heading", { name: "Overview" }).waitFor();
  await admin.page.getByText("Enabled Accounts", { exact: true }).waitFor();
  await admin.page.getByRole("tab", { name: /Usage Trends/ }).click();
  await admin.page.getByText(/Peak hours are not measured/).waitFor();
  await checkLayouts(admin, base, "Cockpit trends");
  await admin.page.getByRole("tab", { name: /Bottlenecks/ }).click();
  await admin.page.getByText(/Headroom is not measured here/).waitFor();
  await checkLayouts(admin, base, "Cockpit bottlenecks");
  await admin.page.getByRole("tab", { name: /360° Overview/ }).click();
  await checkLayouts(admin, base, "Cockpit overview");
  await admin.page.screenshot({ path: `${shots}/${tag}-cockpit.png`, fullPage: true });
  check(admin.errors.length === 0, tag + " cockpit has no JavaScript errors");
  await admin.ctx.close();
}

try {
  for (const base of bases) {
    const tag = base ? "prefix" : "root";
    await home(base, tag);
    await applications(base, tag);
    await cockpit(base, tag);
  }
  console.log(`pilot-review: ${harness.checks()} checks passed`);
} finally {
  await harness.close();
}
