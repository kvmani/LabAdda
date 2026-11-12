// P7 unit administrators: appointment, a branch-only People and Organisation, withdrawal; root and prefix.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-unit-admin";
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
async function appoint(page, base) {
  const drawer = await openProfile(page, base, "Dana Whitfield");
  await press(drawer.getByRole("button", { name: "Make unit administrator", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Make Dana Whitfield a unit administrator", exact: true });
  await choose(dialog, /^Unit to administer/, "Surface Science Division");
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog
    .getByText("Make Dana Whitfield a unit administrator of Surface Science Division", { exact: true })
    .waitFor();
  await reviewAndApply(page, base, dialog, "appoint", "Appoint unit administrator");
  await page.keyboard.press("Escape");
  await page.goto(origin + base + "/admin/org");
  await page.getByText(/Dana Whitfield administers Surface Science Division/).waitFor();
  check(true, base + " the appointment is listed on Organisation");
}
async function work(base) {
  const dana = await login(base, "dana");
  const page = dana.page;
  try {
    await page.getByRole("link", { name: "Administration" }).waitFor();
    await page.goto(origin + base + "/admin");
    await page.getByRole("heading", { name: "People", exact: true }).waitFor();
    const nav = page.getByRole("navigation", { name: "Administration" });
    const links = (await nav.getByRole("link").allInnerTexts()).map((text) => text.trim());
    check(links.join(",") === "People,Organisation", base + " navigation shows only People and Organisation");
    await page.getByRole("button", { name: "View profile for Ben Okafor", exact: true }).waitFor();
    const listed = await page.getByRole("button", { name: /^View profile for / }).allInnerTexts();
    check(
      !listed.some((text) => /Eli Novak|Site Administrator/.test(text)),
      base + " people outside the branch are not listed",
    );
    check(
      (await page.getByRole("button", { name: "Import staff list" }).count()) === 0 &&
        (await page.getByText("Needs attention").count()) === 0,
      base + " site-wide tools are not offered",
    );
    await audit(page, 1400, `${base} unit administrator people`);
    await audit(page, 390, `${base} unit administrator people`);
    await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-people.png` });
    const drawer = await openProfile(page, base, "Ben Okafor");
    check(
      (await drawer.getByRole("button", { name: "Make unit administrator" }).count()) === 0,
      base + " a unit administrator cannot appoint",
    );
    await press(drawer.getByRole("button", { name: "Transfer to another unit", exact: true }));
    const dialog = page.getByRole("dialog", { name: /^Transfer Ben Okafor/ });
    await chooseUnit(dialog, /^New home unit/, "Catalysis Section");
    await press(dialog.getByRole("button", { name: "Next", exact: true }));
    await press(dialog.getByRole("button", { name: "Review change", exact: true }));
    await reviewAndApply(page, base, dialog, "transfer", "Transfer Ben Okafor");
    await drawer.getByText("Catalysis Section", { exact: true }).first().waitFor();
    check(true, base + " transfer inside the branch applied");
    await page.keyboard.press("Escape");
    await page.goto(origin + base + "/admin/org");
    await page.getByRole("treeitem", { name: /Surface Science Division/ }).waitFor();
    check(
      (await page.getByRole("treeitem", { name: /Northwind Research/ }).count()) === 0,
      base + " the chart starts at the administered unit",
    );
    await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-org.png` });
  } finally {
    await dana.context.close();
  }
}
async function withdraw(page, base) {
  await page.goto(origin + base + "/admin/org");
  await press(
    page.getByRole("button", { name: "Withdraw Dana Whitfield from Surface Science Division", exact: true }),
  );
  const dialog = page.getByRole("dialog", {
    name: "Withdraw Dana Whitfield as unit administrator of Surface Science Division",
    exact: true,
  });
  await reviewAndApply(page, base, dialog, "withdraw", "Withdraw appointment");
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await appoint(admin.page, base);
      await work(base);
      await withdraw(admin.page, base);
    } finally {
      await admin.context.close();
    }
    const dana = await login(base, "dana");
    try {
      await dana.page.goto(origin + base + "/admin/people");
      await dana.page
        .getByText("Go to your home workspace")
        .waitFor({ timeout: 10000 })
        .catch(() => {});
      check(
        !(await dana.page.getByRole("link", { name: "Administration" }).count()) &&
          !dana.page.url().includes("/admin/people"),
        base + " after withdrawal the administration pages are gone",
      );
    } finally {
      await dana.context.close();
    }
  }
  console.log(`${checks} unit administrator browser checks passed`);
} finally {
  await browser.close();
}
