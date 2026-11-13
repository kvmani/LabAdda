// Actual browser evidence for branding, private board persistence, isolation and drafts.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8080";
const output = process.env.LABADDA_E2E_SHOTS ?? "/tmp/labadda-personal-board";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let count = 0;
function check(value, label) {
  if (!value) throw new Error(label);
  count++;
  console.log(`PASS ${label}`);
}
async function login(base, username) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/login");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for/ }).waitFor();
  return { context, page };
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const tag = base ? "prefix" : "root";
    const guest = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await guest.goto(origin + base + "/");
    await guest.getByRole("heading", { name: /A place for ideas/ }).waitFor();
    check(
      await guest
        .locator('img[src$="research-board.png"]')
        .evaluate((img) => img.complete && img.naturalWidth > 0),
      `${tag}: bundled research artwork loads`,
    );
    await guest.screenshot({ path: `${output}/${tag}-after-home.png`, fullPage: true });
    await guest.setViewportSize({ width: 390, height: 844 });
    check(
      await guest.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `${tag}: landing fits phone width`,
    );
    await guest.screenshot({ path: `${output}/${tag}-after-home-mobile.png`, fullPage: true });
    await guest.close();
    const { context, page } = await login(base, "asha");
    await page.getByRole("heading", { name: /Welcome,/ }).waitFor();
    await page.screenshot({ path: `${output}/${tag}-after-signed-in.png`, fullPage: true });
    await context.close();
    const owner = await login(base, "asha");
    await owner.page.getByRole("link", { name: "My Whiteboard" }).first().click();
    await owner.page.getByLabel("Sticky note text").fill("Private tensile test discussion — Asha");
    await owner.page.getByRole("button", { name: "Add sticky note", exact: true }).click();
    const note = owner.page.getByRole("button", {
      name: "Private tensile test discussion — Asha",
      exact: true,
    });
    await note.waitFor();
    await owner.page.getByRole("link", { name: "My day", exact: true }).click();
    await owner.page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .waitFor();
    check(true, `${tag}: unsaved draft survives client-side navigation`);
    const noteBox = await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .boundingBox();
    const oldX = await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .locator("..")
      .getAttribute("x");
    await owner.page.mouse.move(noteBox.x + noteBox.width / 2, noteBox.y + noteBox.height / 2);
    await owner.page.mouse.down();
    await owner.page.mouse.move(noteBox.x + noteBox.width / 2 + 60, noteBox.y + noteBox.height / 2 + 20, {
      steps: 5,
    });
    await owner.page.mouse.up();
    const newX = await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .locator("..")
      .getAttribute("x");
    check(Number(newX) > Number(oldX), `${tag}: sticky notes can be dragged`);
    await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .focus();
    await owner.page.keyboard.press("ArrowRight");
    const keyX = await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .locator("..")
      .getAttribute("x");
    check(Number(keyX) > Number(newX), `${tag}: sticky notes also move with the keyboard`);
    await owner.page.getByRole("button", { name: "Draw", exact: true }).click();
    const canvas = owner.page.getByRole("group", { name: "Personal drawing canvas" });
    const bounds = await canvas.boundingBox();
    await owner.page.mouse.move(bounds.x + bounds.width * 0.3, bounds.y + bounds.height * 0.6);
    await owner.page.mouse.down();
    await owner.page.mouse.move(bounds.x + bounds.width * 0.5, bounds.y + bounds.height * 0.3, { steps: 12 });
    await owner.page.mouse.move(bounds.x + bounds.width * 0.7, bounds.y + bounds.height * 0.35, {
      steps: 12,
    });
    await owner.page.mouse.up();
    await owner.page.getByRole("button", { name: "Save board", exact: true }).click();
    await owner.page.getByRole("status").filter({ hasText: "Saved version loaded" }).waitFor();
    await owner.page.reload();
    await owner.page
      .getByRole("button", { name: "Private tensile test discussion — Asha", exact: true })
      .waitFor();
    check(
      (await owner.page.locator("polyline").count()) > 0,
      `${tag}: drawing and sticky note persist after reload`,
    );
    await owner.page.screenshot({ path: `${output}/${tag}-after-personal-board.png`, fullPage: true });
    await owner.page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
    const violations = await owner.page.evaluate(async () =>
      (
        await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
        })
      ).violations.map((item) => item.id),
    );
    check(violations.length === 0, `${tag}: private board accessibility ${JSON.stringify(violations)}`);
    await owner.page.setViewportSize({ width: 390, height: 844 });
    check(
      await owner.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      `${tag}: private board fits phone width`,
    );
    await owner.page.screenshot({ path: `${output}/${tag}-after-personal-board-mobile.png`, fullPage: true });
    const mobileViolations = await owner.page.evaluate(async () =>
      (
        await window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
        })
      ).violations.map((item) => item.id),
    );
    check(mobileViolations.length === 0, `${tag}: phone accessibility ${JSON.stringify(mobileViolations)}`);
    await owner.page.setViewportSize({ width: 1440, height: 1000 });

    for (const username of ["bharat", "admin"]) {
      const other = await login(base, username);
      const result = await other.context.request.get(origin + base + "/api/v1/me/whiteboard");
      check(
        !(await result.text()).includes("Private tensile test discussion"),
        `${tag}: ${username} cannot read Asha's board`,
      );
      await other.context.close();
    }
    await owner.page.getByLabel("Sticky note text").fill("First pending save");
    await owner.page.getByRole("button", { name: "Add sticky note", exact: true }).click();
    let releaseSave;
    let markStarted;
    const heldSave = new Promise((resolve) => {
      releaseSave = resolve;
    });
    const saveStarted = new Promise((resolve) => {
      markStarted = resolve;
    });
    await owner.page.route("**/api/v1/me/whiteboard", async (route) => {
      if (route.request().method() !== "PUT") return route.continue();
      const response = await route.fetch();
      markStarted();
      await heldSave;
      await route.fulfill({ response });
    });
    await owner.page.getByRole("button", { name: "Save board", exact: true }).click();
    await saveStarted;
    await owner.page.getByRole("link", { name: "My day", exact: true }).click();
    await owner.page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await owner.page.getByLabel("Sticky note text").fill("Newer route draft survives old response");
    await owner.page.getByRole("button", { name: "Add sticky note", exact: true }).click();
    const finished = owner.page.waitForResponse(
      (response) => response.url().endsWith("/me/whiteboard") && response.request().method() === "PUT",
    );
    releaseSave();
    await finished;
    await owner.page.getByRole("link", { name: "My day", exact: true }).click();
    await owner.page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await owner.page
      .getByRole("button", { name: "Newer route draft survives old response", exact: true })
      .waitFor();
    check(true, `${tag}: old save response cannot erase a newer route draft`);
    await owner.page.unroute("**/api/v1/me/whiteboard");
    await owner.context.close();
  }
  console.log(`${count} personal board/browser checks passed`);
} finally {
  await browser.close();
}
