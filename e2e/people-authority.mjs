// P3 reviewed authority changes: promotion, Head appointment, leave and retirement, at root and prefix.
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
async function promote(page, base) {
  const drawer = await openProfile(page, base, "Chitra Iyer");
  await press(drawer.getByRole("button", { name: "Promote or change role", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Promote Chitra Iyer", exact: true });
  await dialog.getByLabel("Designation", { exact: true }).fill("Scientific Officer D");
  await choose(dialog, "Change the role in", "Corrosion Section (now member)");
  await choose(dialog, "New role", "Steward");
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog
    .getByText("Set the role of Chitra Iyer in Corrosion Section to steward", { exact: true })
    .waitFor();
  check(
    (await dialog.innerText()).includes("Chitra Iyer will be able to moderate Corrosion Section"),
    base + " promotion says moderation powers change",
  );
  await reviewAndApply(page, base, dialog, "promote", "Promote Chitra Iyer");
  await drawer.getByText("Scientific Officer D", { exact: true }).waitFor();
  check(true, base + " profile shows the new designation");
  await page.keyboard.press("Escape");
}
async function appointHead(page, base) {
  const drawer = await openProfile(page, base, "Deepa Nair");
  await press(drawer.getByRole("button", { name: "Appoint to a position", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Appoint Deepa Nair to a position", exact: true });
  await choose(dialog, /^Unit/, "Surface Engineering Division");
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog
    .getByText("Appoint Deepa Nair as Head of Surface Engineering Division", { exact: true })
    .waitFor();
  await reviewAndApply(page, base, dialog, "appoint", "Appoint Deepa Nair");
  await drawer.getByText("Head of Surface Engineering Division", { exact: true }).waitFor();
  check(true, base + " profile lists the Head position");
  await page.keyboard.press("Escape");
}
async function leave(page, base) {
  const drawer = await openProfile(page, base, "Bharat Kulkarni");
  await press(drawer.getByRole("button", { name: "Record long leave", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Record long leave for Bharat Kulkarni", exact: true });
  await dialog.getByLabel(/^Expected return date/).fill(day(90));
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog
    .getByText("Set the employment status of Bharat Kulkarni to on leave", { exact: true })
    .waitFor();
  await reviewAndApply(page, base, dialog, "leave", "Record leave");
  await drawer.getByText("on leave", { exact: true }).waitFor();
  check(true, base + " profile shows on leave");
  await page.keyboard.press("Escape");
}
async function retire(page, base) {
  const drawer = await openProfile(page, base, "Deepa Nair");
  await press(drawer.getByRole("button", { name: "Retire or leave", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Retire or leave: Deepa Nair", exact: true });
  await dialog.getByLabel(/^Keep Project Tejas/).waitFor();
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog.getByText(/Choose who takes over as Head of Surface Engineering Division/).waitFor();
  check(true, base + " retirement is blocked until a successor is chosen");
  await choose(dialog, "Successor in Surface Engineering Division", "Asha Rao");
  await dialog.getByLabel(/^Acting appointment/).check();
  await dialog.getByLabel(/^Acting until/).fill(day(60));
  await choose(dialog, "New steward of Project Tejas", "Esha Menon");
  await dialog.getByText(/Appoint Asha Rao as acting Head of Surface Engineering Division until/).waitFor();
  const review = await dialog.innerText();
  check(review.includes("Set the role of Esha Menon in Project Tejas to steward"), base + " group successor");
  check(review.includes("end their sign-in and open sessions"), base + " retirement ends sign-in");
  await reviewAndApply(page, base, dialog, "retire", "Close the account of Deepa Nair");
  await drawer.getByText("retired", { exact: true }).waitFor();
  check(true, base + " profile shows retired");
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await promote(admin.page, base);
      await appointHead(admin.page, base);
      await leave(admin.page, base);
      await retire(admin.page, base);
    } finally {
      await admin.context.close();
    }
    const deepa = await browser.newContext();
    const page = await deepa.newPage();
    await page.goto(origin + base + "/");
    await page.getByLabel("Username", { exact: true }).fill("deepa");
    await page.getByLabel("Password", { exact: true }).fill("fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("alert").first().waitFor();
    check(
      !(await page.getByRole("button", { name: /^Account menu for / }).count()),
      base + " retired Deepa cannot sign in",
    );
    await deepa.close();
  }
  console.log(`${checks} people authority browser checks passed`);
} finally {
  await browser.close();
}
