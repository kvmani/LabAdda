// Shared/private selection, movement and bundled fonts at root and prefixed instances.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const axe = require("../frontend/node_modules/axe-core");
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8080";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
function check(value, label) {
  if (!value) throw new Error(label);
  console.log(`PASS ${label}`);
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
    const page = await context.newPage();
    const errors = [];
    const external = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (request) => {
      if (!request.url().startsWith(origin) && !request.url().startsWith("data:"))
        external.push(request.url());
    });
    await page.goto(`${origin}${base}/login`);
    await page.getByLabel("Username").fill("bharat");
    await page.getByLabel("Password").fill("fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: /^Account menu for/ }).waitFor();
    const list = await (await context.request.get(`${origin}${base}/api/v1/workspaces`)).json();
    const section = list.workspaces.find((ws) => ws.name === "Thin Films Section").id;
    await page.goto(`${origin}${base}/w/${section}/board`);
    await page.getByRole("button", { name: "🗒 Sticky", exact: true }).click();
    const canvas = page.getByLabel("Drawing canvas. Use the list view for a text alternative.");
    await canvas.click({ position: { x: 200, y: 100 } });
    await page.getByLabel("Note text", { exact: true }).fill("Shared tensile discussion");
    await page.getByLabel("Font", { exact: true }).selectOption("handwritten");
    await page.getByLabel("Font size", { exact: true }).selectOption("24");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await page.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    await page.getByRole("button", { name: "↖ Select", exact: true }).click();
    await canvas.click({ position: { x: 220, y: 120 } });
    await page.getByRole("button", { name: "Edit selected item", exact: true }).waitFor();
    check(true, "shared sticky can be selected without opening a modal");
    const moving = page.waitForResponse(
      (r) => r.url().includes("/board/ops") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Move right", exact: true }).click();
    check((await moving).status() === 200, "selected sticky moves with keyboard-accessible control");
    await page.getByRole("button", { name: "Edit selected item", exact: true }).click();
    await page.getByLabel("Font", { exact: true }).selectOption("serif");
    await page.getByLabel("Font size", { exact: true }).selectOption("32");
    const editing = page.waitForResponse(
      (r) => r.url().includes("/board/ops") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    check((await editing).status() === 200, "selected sticky formatting commits atomically");
    await page.reload();
    const state = await (
      await context.request.get(`${origin}${base}/api/v1/workspaces/${section}/board`)
    ).json();
    check(
      state.ops.some((op) => op.payload?.data?.font_family === "serif" && op.payload?.data?.font_size === 32),
      "shared font and size survive reload",
    );
    await page.getByRole("button", { name: "↖ Select", exact: true }).click();
    const box = await canvas.boundingBox();
    const dragResponse = page.waitForResponse(
      (r) => r.url().includes("/board/ops") && r.request().method() === "POST",
    );
    await page.mouse.move(box.x + 230, box.y + 125);
    await page.mouse.down();
    await page.mouse.move(box.x + 260, box.y + 145, { steps: 6 });
    await page.mouse.up();
    const moved = (await (await dragResponse).json()).committed;
    check(
      moved.type === "move" && moved.payload.dx > 0 && moved.payload.dy > 0,
      "selected shared note drags and commits position",
    );
    await page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await page.getByRole("button", { name: "Add sticky note", exact: true }).click();
    await page.getByLabel("Note text", { exact: true }).fill("Private tensile discussion");
    await page.getByLabel("Font", { exact: true }).selectOption("handwritten");
    await page.getByLabel("Font size", { exact: true }).selectOption("24");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await page.getByText(/^Board items/).click();
    await page.getByRole("button", { name: "Select item", exact: true }).click();
    await page.getByRole("button", { name: "Move down", exact: true }).click();
    await page.getByRole("button", { name: "💾 Save", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".save-state")?.textContent === "Saved");
    const privateState = await (await context.request.get(`${origin}${base}/api/v1/me/whiteboard`)).json();
    check(
      privateState.objects[0].font_family === "handwritten" && privateState.objects[0].font_size === 24,
      "private font and size persist",
    );
    check(privateState.objects[0].y > 0, "private selected item can move down");
    await page.reload();
    await page.getByLabel("Whiteboard drawing surface", { exact: true }).waitFor();
    await page.waitForFunction(() => document.fonts.check('16px "LabAdda Handwriting"'));
    check(
      await page.evaluate(() => document.fonts.check('16px "LabAdda Handwriting"')),
      "handwritten font loads from bundled assets",
    );
    await page.getByText(/^Board items/).click();
    await page.getByRole("button", { name: "Select item", exact: true }).click();
    await page.getByRole("button", { name: "Edit selected item", exact: true }).click();
    for (const width of [1400, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.addScriptTag({ content: axe.source });
      const violations = await page.evaluate(
        async () =>
          (await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } })).violations,
      );
      if (violations.length)
        console.log(
          JSON.stringify(
            violations.map((item) => ({
              id: item.id,
              nodes: item.nodes.map((node) => ({ html: node.html, reason: node.failureSummary })),
            })),
            null,
            2,
          ),
        );
      check(violations.length === 0, `board editor accessibility at ${width}px`);
    }
    check(external.length === 0, "board fonts and editing make no external requests");
    check(errors.length === 0, `no browser exceptions (${errors.join(",")})`);
    await page.screenshot({
      path: `/tmp/labadda-${base ? "prefix" : "root"}-board-editing.png`,
      fullPage: true,
    });
    await context.close();
  }
} finally {
  await browser.close();
}
