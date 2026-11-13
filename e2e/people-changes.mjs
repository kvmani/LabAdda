// P2 reviewed changes: add a person and transfer Bharat by keyboard and buttons, at root and prefix.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-people-changes";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
async function login(base, username) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { context, page };
}
async function audit(page, width, label) {
  await page.setViewportSize({ width, height: 1100 });
  await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((item) => item.id + "@" + item.nodes.map((node) => node.target.join(" ")).join(";")),
  );
  check(violations.length === 0, `${label} accessibility ${width}: ${violations}`);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}`,
  );
  await page.setViewportSize({ width: 1400, height: 1100 });
}
/** Buttons are reached and pressed from the keyboard; no pointer clicks in the change flows. */
async function press(locator) {
  // A trial click only waits until the control is visible, enabled and stable; it does not click.
  await locator.click({ trial: true });
  await locator.focus();
  await locator.page().keyboard.press("Enter");
}
async function chooseUnit(dialog, label, unitName) {
  const select = dialog.getByLabel(label);
  const value = await select.evaluate(
    (element, name) => [...element.options].find((option) => option.text.endsWith(name))?.value,
    unitName,
  );
  await select.focus();
  await select.selectOption(value);
}
async function addPerson(page, base) {
  await page.goto(origin + base + "/admin/people");
  await press(page.getByRole("button", { name: "Add person", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Add person", exact: true });
  await dialog.getByText("Step 1 of 4: Details", { exact: true }).waitFor();
  await dialog.getByLabel(/^Full name/).fill("Gita Sen");
  await dialog.getByLabel(/^Username/).fill("gita.sen");
  await dialog.getByLabel("Employee number", { exact: true }).fill("NM-410");
  await dialog.getByLabel("Designation", { exact: true }).fill("Scientific Officer C");
  await press(dialog.getByRole("button", { name: "Next", exact: true }));
  await chooseUnit(dialog, /^Home unit/, "Corrosion Section");
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog.getByText("Create an invited account for Gita Sen (gita.sen)", { exact: true }).waitFor();
  check(
    await dialog.getByText("Make Corrosion Section the home unit of Gita Sen, as member").isVisible(),
    base + " add review names the home unit and role",
  );
  await dialog.getByLabel(/^Reason for this change/).fill("New joiner in Corrosion");
  await audit(page, 1400, base + " add review");
  await audit(page, 390, base + " add review");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-add-review.png` });
  await press(dialog.getByRole("button", { name: "Add person", exact: true }));
  const slip = dialog.getByRole("region", { name: "Activation slip" });
  await slip.waitFor();
  const code = (await slip.locator(".people-slip__code").innerText()).trim();
  check(code.length >= 10, base + " slip shows the one-time code");
  check(
    (await slip.innerText()).includes(origin + base + "/activate"),
    base + " slip shows the sign-in address for this instance",
  );
  await audit(page, 1400, base + " activation slip");
  await audit(page, 390, base + " activation slip");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-activation-slip.png` });
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  const profile = page.getByRole("dialog", { name: "Gita Sen", exact: true });
  await profile.getByText("invited", { exact: true }).waitFor();
  check(!(await profile.innerText()).includes(code), base + " code is not shown again after the slip");
  const fresh = await newCode(page, profile, base);
  check(fresh !== code, base + " a lost slip can be replaced with a new code");
  await page.keyboard.press("Escape");
  return fresh;
}
async function newCode(page, profile, base) {
  await press(profile.getByRole("button", { name: "Issue a new activation code", exact: true }));
  const confirm = page.getByRole("dialog", { name: "New activation code for Gita Sen", exact: true });
  await confirm.getByLabel(/^Reason for a new code/).fill("Slip was lost");
  await press(confirm.getByRole("button", { name: "Issue new code", exact: true }));
  const dialog = page.getByRole("dialog", { name: "New activation code", exact: true });
  const slip = dialog.getByRole("region", { name: "Activation slip" });
  await slip.waitFor();
  const code = (await slip.locator(".people-slip__code").innerText()).trim();
  await audit(page, 390, base + " new activation code");
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  return code;
}
async function activate(base, code) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(origin + base + "/activate?token=" + encodeURIComponent(code));
  await page.getByLabel(/^New password/).fill("gita-new-password");
  await page.getByLabel(/^Confirm password/).fill("gita-new-password");
  await press(page.getByRole("button", { name: "Activate account", exact: true }));
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  check(true, base + " new person activates with the slip code");
  await context.close();
}
async function transfer(page, base) {
  await page.goto(origin + base + "/admin/people?q=Bharat");
  await press(page.getByRole("button", { name: "View profile for Bharat Kulkarni", exact: true }));
  const drawer = page.getByRole("dialog", { name: "Bharat Kulkarni", exact: true });
  await press(drawer.getByRole("button", { name: "Transfer to another unit", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Transfer Bharat Kulkarni", exact: true });
  await chooseUnit(dialog, /^New home unit/, "Corrosion Section");
  await press(dialog.getByRole("button", { name: "Next", exact: true }));
  const keepGroup = dialog.getByLabel("Keep Microscopy Journal Club (group, steward)");
  await keepGroup.waitFor();
  check(await keepGroup.isChecked(), base + " projects and groups are kept by default");
  check(
    !(await dialog.getByLabel(/^Keep access to Thin Films Section/).isChecked()),
    base + " old unit is removed by default",
  );
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog.getByText("Remove Bharat Kulkarni from Thin Films Section", { exact: true }).waitFor();
  const review = await dialog.innerText();
  check(
    review.includes("Bharat Kulkarni will be able to read Corrosion Section."),
    base + " access gained shown",
  );
  check(
    review.includes("Bharat Kulkarni will no longer be able to read Thin Films Section."),
    base + " access lost",
  );
  check(review.includes("Before: Thin Films Section"), base + " review shows the home unit before");
  await dialog.getByLabel(/^Reason for this change/).fill("Moves to Corrosion");
  await audit(page, 1400, base + " transfer review");
  await audit(page, 390, base + " transfer review");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-transfer-review.png` });
  await press(dialog.getByRole("button", { name: "Transfer Bharat Kulkarni", exact: true }));
  await dialog.getByText(/now has .*Corrosion Section as their home unit/).waitFor();
  check(true, base + " transfer confirmed after commit");
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  await drawer.getByText("Corrosion Section", { exact: true }).waitFor();
  check(true, base + " profile shows the new home unit");
}
async function verifyReads(base) {
  const bharat = await login(base, "bharat");
  const admin = await login(base, "admin");
  try {
    const endpoint = origin + base + "/api/v1";
    const units = (await (await admin.context.request.get(endpoint + "/admin/workspaces")).json()).workspaces;
    const id = (name) => units.find((unit) => unit.name === name).id;
    const old = await bharat.context.request.get(endpoint + "/workspaces/" + id("Thin Films Section"));
    check(old.status() === 404, base + " Bharat's later read of Thin Films is the uniform 404");
    const next = await bharat.context.request.get(endpoint + "/workspaces/" + id("Corrosion Section"));
    check(next.status() === 200, base + " Bharat reads Corrosion");
    const session = await (await bharat.context.request.get(endpoint + "/auth/session")).json();
    const request = {
      kind: "transfer",
      person_id: session.user.id,
      to_unit_id: id("Thin Films Section"),
      role: "member",
    };
    const preview = await bharat.context.request.post(endpoint + "/admin/changes/preview", {
      headers: { "X-CSRF-Token": session.csrf_token },
      data: { request },
    });
    check(preview.status() === 403, base + " member cannot use the change API");
  } finally {
    await Promise.all([bharat.context.close(), admin.context.close()]);
  }
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      const code = await addPerson(admin.page, base);
      await activate(base, code);
      await transfer(admin.page, base);
    } finally {
      await admin.context.close();
    }
    await verifyReads(base);
  }
  console.log(`${checks} people change browser checks passed`);
} finally {
  await browser.close();
}
