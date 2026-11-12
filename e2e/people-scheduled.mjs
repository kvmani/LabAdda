// P5 scheduled changes and the attention list: schedule, list, cancel, at root and prefix.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-people-scheduled";
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
    ).violations.map((item) => item.id),
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
function day(offset) {
  return new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);
}
async function choose(dialog, label, text) {
  const select = dialog.getByLabel(label);
  await select.waitFor();
  const value = await select.evaluate(
    (element, wanted) =>
      [...element.options].find(
        (option) =>
          option.text === wanted || option.text.endsWith(wanted) || option.text.startsWith(wanted + " ("),
      )?.value,
    text,
  );
  assert.ok(value, `option ${text} in ${label}`);
  await select.focus();
  await select.selectOption(value);
}
async function openProfile(page, base, name) {
  await page.goto(origin + base + "/admin/people?q=" + encodeURIComponent(name.split(" ")[0]));
  await press(page.getByRole("button", { name: "View profile for " + name, exact: true }));
  return page.getByRole("dialog", { name, exact: true });
}
async function reviewAndApply(page, base, dialog, shot, confirm) {
  await dialog.getByText("What will happen", { exact: true }).waitFor();
  await dialog.getByLabel(/^Reason for this change/).fill("Scenario staff change");
  await audit(page, 1400, `${base} ${shot} review`);
  await audit(page, 390, `${base} ${shot} review`);
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-${shot}-review.png` });
  await press(dialog.getByRole("button", { name: confirm, exact: true }));
  await dialog.getByRole("button", { name: "Done", exact: true }).waitFor();
  check(true, `${base} ${shot} confirmed after commit`);
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
}
async function schedule(page, base) {
  const drawer = await openProfile(page, base, "Ben Okafor");
  await press(drawer.getByRole("button", { name: "Record long leave", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Record long leave for Ben Okafor", exact: true });
  await dialog.getByLabel(/^Expected return date/).fill(day(90));
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog.getByText("Set the employment status of Ben Okafor to on leave", { exact: true }).waitFor();
  await choose(dialog, "When should this happen?", "At the start of a later day");
  await dialog.getByLabel(/^Day it takes effect/).fill(day(3));
  await dialog.getByText("Set the employment status of Ben Okafor to on leave", { exact: true }).waitFor();
  await dialog.getByLabel(/^Reason for this change/).fill("Leave starts with the new term");
  await audit(page, 1400, `${base} schedule review`);
  await audit(page, 390, `${base} schedule review`);
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-schedule-review.png` });
  await press(dialog.getByRole("button", { name: "Schedule change", exact: true }));
  await dialog.getByText(/Nothing changes until then/).waitFor();
  check(true, base + " change scheduled and nothing applied");
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  await drawer.getByText("Scheduled changes for this person", { exact: true }).waitFor();
  check(
    (await drawer.innerText()).includes("Set the employment status of Ben Okafor to on leave"),
    base + " profile lists the scheduled change",
  );
  check(!(await drawer.getByText("on leave", { exact: true }).count()), base + " Ben is not on leave yet");
  await page.keyboard.press("Escape");
}
async function overview(page, base) {
  await page.goto(origin + base + "/admin/people");
  const list = page.getByRole("region", { name: "Scheduled changes", exact: true });
  await list.getByText(/Leave on /).waitFor();
  const attention = page.getByRole("region", { name: "Needs attention", exact: true });
  await attention
    .getByRole("link", { name: /fixes this/ })
    .first()
    .waitFor();
  check(true, base + " People page lists scheduled changes and the attention list");
  await audit(page, 1400, `${base} people overview`);
  await audit(page, 390, `${base} people overview`);
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-overview.png`, fullPage: true });
  await press(list.getByRole("button", { name: "Cancel this change", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Cancel scheduled change", exact: true });
  await dialog.getByLabel(/^Reason/).fill("Plans changed");
  await press(dialog.getByRole("button", { name: "Cancel this change", exact: true }));
  await list.getByText("No changes are scheduled.").waitFor();
  check(true, base + " cancelled change leaves the list");
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await schedule(admin.page, base);
      await overview(admin.page, base);
    } finally {
      await admin.context.close();
    }
  }
  console.log(`${checks} people scheduled browser checks passed`);
} finally {
  await browser.close();
}
