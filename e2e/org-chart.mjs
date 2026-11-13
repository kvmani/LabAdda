// P4 organisation chart: keyboard path, split and merge (scenario steps 5 and 6), drag gestures
// that only open a review, and real reads afterwards, at the root and the prefixed instance.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-org-chart";
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
  await page.setViewportSize({ width: 1400, height: 1100 });
}
/** Buttons are reached and pressed from the keyboard. */
async function press(locator) {
  await locator.click({ trial: true });
  await locator.focus();
  await locator.page().keyboard.press("Enter");
}
const unit = (page, name) => page.getByRole("treeitem", { name: new RegExp(name) });
async function confirm(dialog, button, reason) {
  await dialog.getByLabel(/^Reason for this change/).fill(reason);
  await press(dialog.getByRole("button", { name: button, exact: true }));
}
async function keyboardPath(page, base) {
  await page.goto(origin + base + "/admin/org");
  const tree = page.getByRole("tree", { name: "Organisation units" });
  await tree.waitFor();
  check((await tree.getByRole("treeitem").count()) === 5, base + " chart shows the five fixture units");
  await audit(page, 1400, base + " chart");
  await audit(page, 390, base + " chart");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-chart.png` });
  await unit(page, "National Materials Research Laboratory").focus();
  for (const key of ["ArrowDown", "ArrowDown", "ArrowDown", "ArrowRight"]) await page.keyboard.press(key);
  const focused = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
  check(
    focused?.startsWith("TFS, Thin Films Section"),
    base + " arrow keys reach Thin Films Section: " + focused,
  );
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Thin Films Section", exact: true }).waitFor();
  check(true, base + " Enter opens the unit panel");
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  check(await page.getByText("Zoom 125%").isVisible(), base + " zoom in changes the zoom");
  await page.getByRole("button", { name: "Fit to screen", exact: true }).click();
  check(await page.getByText("Zoom 100%").isVisible(), base + " fit shows the whole chart at real size");
  await page.keyboard.press("Escape");
}
async function split(page, base) {
  await press(page.getByRole("button", { name: "Split off a new unit…", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Split a new unit from Thin Films Section" });
  await dialog.getByLabel(/^New unit name/).fill("Sensors Section");
  await dialog.getByLabel(/^New unit code/).fill("sed-se");
  await dialog.getByLabel("Bharat Kulkarni", { exact: true }).check();
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog
    .getByText("Create the unit Sensors Section (SED-SE) under Surface Engineering Division")
    .waitFor();
  const acknowledge = dialog.getByLabel("I understand a unit will be left with no steward");
  await acknowledge.check();
  await dialog
    .getByText(/Bharat Kulkarni/)
    .first()
    .waitFor();
  await dialog.getByText("1 person will no longer be able to read Thin Films Section.").waitFor();
  check(true, base + " split review counts who loses access");
  await audit(page, 1400, base + " split review");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-split-review.png` });
  await confirm(dialog, "Split unit", "Sensors becomes its own section");
  await dialog.getByText("Sensors Section now exists and its people have moved.").waitFor();
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  await unit(page, "SED-SE, Sensors Section").waitFor();
  check(true, base + " the new unit appears in the chart with its code");
}
async function merge(page, base) {
  await unit(page, "Thin Films Section").click();
  await press(page.getByRole("button", { name: "Merge into…", exact: true }));
  const dialog = page.getByRole("dialog", { name: "Merge Thin Films Section into another unit" });
  const select = dialog.getByLabel(/^Merge into/);
  const value = await select.evaluate(
    (element) => [...element.options].find((option) => option.text.endsWith("Sensors Section"))?.value,
  );
  await select.selectOption(value);
  await press(dialog.getByRole("button", { name: "Review change", exact: true }));
  await dialog.getByText("Close Thin Films Section and keep it readable as history").waitFor();
  await dialog.getByText(/keep read access to the history of Thin Films Section/).waitFor();
  check(true, base + " merge review says members keep history");
  await confirm(dialog, "Merge units", "Thin Films is merged into Sensors");
  await dialog.getByText("Thin Films Section has been merged and closed.").waitFor();
  await press(dialog.getByRole("button", { name: "Done", exact: true }));
  check((await unit(page, "Thin Films Section").count()) === 0, base + " the closed unit leaves the chart");
  await page.getByLabel("Show closed units").check();
  check(
    (await unit(page, "TFS, Thin Films Section. .*closed").count()) === 1,
    base + " it is listed, marked closed, when closed units are shown",
  );
  await page.getByLabel("Show closed units").uncheck();
}
async function centre(page, locator) {
  const box = await locator.boundingBox();
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}
async function drag(page, from, to) {
  const start = await centre(page, from);
  const end = await centre(page, to);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 20, start.y + 20, { steps: 4 });
  await page.mouse.move(end.x, end.y, { steps: 8 });
  await page.mouse.up();
}
async function gestures(page, base) {
  await unit(page, "Corrosion Section").click();
  const person = page.locator(".org-panel__person", { hasText: "Chitra Iyer" });
  await drag(page, person, unit(page, "Sensors Section"));
  const transfer = page.getByRole("dialog", { name: "Transfer Chitra Iyer" });
  await transfer.waitFor();
  check(
    (await transfer.getByLabel(/^New home unit/).inputValue()) !== "",
    base + " dropping a person opens the transfer with the unit chosen",
  );
  await press(transfer.getByRole("button", { name: "Cancel", exact: true }));
  await drag(page, unit(page, "Corrosion Section"), unit(page, "Materials Group"));
  const move = page.getByRole("dialog", { name: "Move Corrosion Section" });
  await move.getByRole("button", { name: "Review change", exact: true }).click();
  await move.getByText(/Move Corrosion Section with its sub-units under Materials Group/).waitFor();
  check(true, base + " dropping a unit opens the move review");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-move-review.png` });
  await press(move.getByRole("button", { name: "Cancel", exact: true }));
  await drag(page, unit(page, "Surface Engineering Division"), unit(page, "Corrosion Section"));
  const blocked = page.getByRole("dialog", { name: "Move Surface Engineering Division" });
  await blocked.getByRole("button", { name: "Review change", exact: true }).click();
  await blocked.getByText("A unit cannot move beneath itself or its own sub-units.").waitFor();
  check(true, base + " moving a unit beneath its own descendant is blocked");
  await press(blocked.getByRole("button", { name: "Cancel", exact: true }));
}
async function reads(base) {
  const bharat = await login(base, "bharat");
  const asha = await login(base, "asha");
  const admin = await login(base, "admin");
  try {
    const endpoint = origin + base + "/api/v1";
    const tree = await (await admin.context.request.get(endpoint + "/admin/org/tree")).json();
    const id = (name) => tree.units.find((item) => item.name === name).id;
    const get = (who, name) => who.context.request.get(endpoint + "/workspaces/" + id(name));
    check((await get(bharat, "Sensors Section")).status() === 200, base + " Bharat reads Sensors");
    check(
      (await get(bharat, "Thin Films Section")).status() === 404,
      base + " Bharat no longer reads Thin Films",
    );
    check(
      (await get(asha, "Thin Films Section")).status() === 200,
      base + " Asha keeps reading closed Thin Films",
    );
    check(
      (await get(admin, "Sensors Section")).status() === 404,
      base + " the administrator has no content access",
    );
    check(JSON.stringify(tree).includes("fixture-pass") === false, base + " the chart data holds no secrets");
  } finally {
    await Promise.all([bharat.context.close(), asha.context.close(), admin.context.close()]);
  }
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await keyboardPath(admin.page, base);
      await unit(admin.page, "Thin Films Section").click();
      await split(admin.page, base);
      await merge(admin.page, base);
      await gestures(admin.page, base);
    } finally {
      await admin.context.close();
    }
    await reads(base);
  }
  console.log(`${checks} organisation chart browser checks passed`);
} finally {
  await browser.close();
}
