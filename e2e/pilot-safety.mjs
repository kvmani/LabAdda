// Pilot regressions on the actual app through nginx, at root and under a prefix.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8080";
const output = process.env.LABADDA_E2E_SHOTS ?? "/tmp/labadda-pilot-review";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
function check(value, label) {
  if (!value) throw new Error(label);
  console.log(`PASS ${label}`);
}
async function request(page, base, path, body, method = "GET") {
  return page.evaluate(
    async ({ base, path, body, method }) => {
      const session = await (await fetch(`${base}/api/v1/auth/session`)).json();
      const response = await fetch(`${base}/api/v1${path}`, {
        method,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      return { status: response.status, body: await response.json() };
    },
    { base, path, body, method },
  );
}
async function addNote(page, text) {
  await page.getByRole("button", { name: "Add sticky note", exact: true }).click();
  await page.getByLabel("Note text", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Save note", exact: true }).click();
}
async function saved(page) {
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/me/whiteboard") && r.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "💾 Save", exact: true }).click();
  check((await response).status() === 200, "private board save commits successfully");
  await page.waitForFunction(() => !document.querySelector(".toolbar")?.textContent.includes("Saving…"));
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const tag = base ? "prefix" : "root";
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      timezoneId: "Asia/Kolkata",
    });
    const page = await context.newPage();
    const errors = [],
      external = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => {
      if (!r.url().startsWith(origin) && !r.url().startsWith("data:")) external.push(r.url());
    });
    await page.goto(origin + base + "/login");
    await page.getByLabel("Username").fill("asha");
    await page.getByLabel("Password").fill("fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: /^Account menu for / }).waitFor();
    await page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await page.getByRole("heading", { name: /My Whiteboard/ }).waitFor();
    await addNote(page, "Asha tensile review draft");
    await page.getByRole("button", { name: /Add Board/ }).click();
    await page.getByRole("tab", { name: /WhiteBoard_2/ }).waitFor();
    await addNote(page, "Second private board — microscopy");
    await saved(page);
    await page.getByRole("tab", { name: /WhiteBoard_1/ }).click();
    await page.getByText(/^Board items/).click();
    await page.getByRole("button", { name: "Asha tensile review draft", exact: true }).waitFor();
    check(true, `${tag}: independent drafts survive board switches`);
    await page.getByRole("link", { name: "My day", exact: true }).first().click();
    await page
      .getByRole("link", { name: /My Whiteboard/ })
      .first()
      .click();
    await page.getByText(/^Board items/).click();
    await page.getByRole("button", { name: "Asha tensile review draft", exact: true }).waitFor();
    check(true, `${tag}: private draft survives SPA navigation`);
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    let held;
    const entered = new Promise((resolve) => {
      held = resolve;
    });
    await page.route("**/api/v1/me/whiteboard", async (route) => {
      if (route.request().method() === "PUT") {
        held();
        await gate;
      }
      await route.continue();
    });
    const save = saved(page);
    await entered;
    await page.getByRole("tab", { name: /WhiteBoard_2/ }).click();
    check(
      (await page.getByRole("tab", { name: /WhiteBoard_1/ }).getAttribute("aria-selected")) === "true",
      `${tag}: cannot switch while a private save is pending`,
    );
    release();
    await save;
    await page.unroute("**/api/v1/me/whiteboard");
    const first = await request(page, base, "/me/whiteboard?board_index=0");
    const second = await request(page, base, "/me/whiteboard?board_index=1");
    check(
      first.body.objects[0].text === "Asha tensile review draft" &&
        second.body.objects[0].text === "Second private board — microscopy",
      `${tag}: private boards persisted separately`,
    );
    check(
      first.body.objects[0].id.match(/^[0-9a-f-]{36}$/),
      `${tag}: private object IDs meet the UUID contract`,
    );
    await page.screenshot({ path: `${output}/${tag}-private-board.png`, fullPage: true });
    const workspaces = await request(page, base, "/workspaces");
    const ws = workspaces.body.workspaces.find((w) => w.name === "Thin Films Section").id;
    const path = `/workspaces/${ws}/board`;
    for (const board_index of [0, 1]) {
      const result = await request(
        page,
        base,
        path + "/ops",
        {
          op_id: crypto.randomUUID(),
          epoch: 1,
          board_index,
          type: "add",
          object_id: "pilot-sticky",
          payload: {
            kind: "sticky",
            data: { x: 100, y: 100, text: `Board ${board_index} tensile review`, color: "#fff59d" },
          },
        },
        "POST",
      );
      check(result.status === 200, `${tag}: seed shared board ${board_index}`);
    }
    await page.goto(origin + base + `/w/${ws}/board`);
    await page.getByRole("tab", { name: /WhiteBoard_1/ }).waitFor();
    // Create a named tab through the API so the real UI refreshes its complete tab list.
    await request(page, base, `/workspaces/${ws}/boards/1`, { title: "Tensile" }, "PATCH");
    await page.reload();
    await page.getByRole("tab", { name: /Tensile/ }).click();
    await page.getByRole("button", { name: "List view", exact: true }).click();
    await page.getByText("Sticky: Board 1 tensile review", { exact: false }).waitFor();
    check(
      await page.getByRole("button", { name: "Create task from board", exact: true }).isDisabled(),
      `${tag}: unindexed task reference disabled on secondary board`,
    );
    check(
      await page.getByRole("button", { name: /Open on touch panel/ }).isDisabled(),
      `${tag}: panel pairing clearly restricted to first board`,
    );
    // Editing is one durable update; the original is never erased first.
    await page.getByRole("button", { name: /Select$/ }).click();
    const canvas = page.getByRole("img", { name: /Drawing canvas/ });
    const box = await canvas.boundingBox();
    await page.mouse.click(box.x + 135, box.y + 135);
    // Selecting only selects (so a note can be dragged); editing is its own explicit step.
    await page.getByRole("button", { name: "Edit selected item", exact: true }).click();
    await page.getByLabel("Note text", { exact: true }).fill("Revised board 1 tensile review");
    const editResponse = page.waitForResponse(
      (r) => r.url().endsWith("/board/ops") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    const edited = await editResponse;
    check(
      edited.request().postDataJSON().type === "update" && edited.status() === 200,
      `${tag}: sticky edits commit atomically`,
    );
    await page.getByText("Sticky: Revised board 1 tensile review", { exact: false }).waitFor();
    await page.screenshot({ path: `${output}/${tag}-shared-secondary-board.png`, fullPage: true });
    await page.getByRole("button", { name: /Publish snapshot/ }).click();
    await page.mouse.move(box.x + 70, box.y + 70);
    await page.mouse.down();
    await page.mouse.move(box.x + 330, box.y + 250, { steps: 5 });
    await page.mouse.up();
    const preview = page.getByAltText("Preview of the selected board region");
    await preview.waitFor();
    check(
      (await preview.getAttribute("src")).includes("board_index=1"),
      `${tag}: snapshot preview uses the selected board`,
    );
    await page.getByLabel("Summary", { exact: true }).fill("Secondary tensile board snapshot");
    const snapshotResponse = page.waitForResponse(
      (r) => r.url().endsWith("/board/snapshots") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /Publish to Thin Films Section/ }).click();
    const published = await snapshotResponse;
    check(
      published.status() === 201 || published.status() === 200,
      `${tag}: publish selected secondary snapshot`,
    );
    check(
      published.request().postDataJSON().board_index === 1,
      `${tag}: snapshot publication keeps the board index`,
    );
    await page.getByRole("dialog", { name: "Publish snapshot", exact: true }).waitFor({ state: "hidden" });
    check(
      (await page.getByRole("tab", { name: /Tensile/ }).getAttribute("aria-selected")) === "true",
      `${tag}: publishing keeps the selected board`,
    );
    page.once("dialog", (dialog) => {
      console.log("RESTORE DIALOG", dialog.type(), dialog.message());
      return dialog.accept("0");
    });
    const [restored] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith("/board/restore")),
      page.getByRole("button", { name: "Restore…", exact: true }).click(),
    ]);
    check(
      restored.request().postDataJSON().board_index === 1 && restored.status() === 200,
      `${tag}: restore targets the selected board`,
    );
    check(
      (await request(page, base, path)).body.epoch === 1,
      `${tag}: secondary restore leaves the first board unchanged`,
    );
    // Calendar UI carries revisions and preserves a rejected edit in its dialog.
    await page.goto(origin + base + "/calendar");
    await page
      .getByRole("button", { name: /Create/, exact: false })
      .first()
      .click();
    await page.getByLabel("Event Title", { exact: true }).fill("Asha pilot calendar review");
    const createResponse = page.waitForResponse(
      (r) => r.url().endsWith("/calendar/events") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Save", exact: true }).click();
    const created = await createResponse;
    check(created.status() === 200, `${tag}: create calendar event in browser`);
    const event = await created.json();
    await page.getByText("Asha pilot calendar review", { exact: true }).first().click();
    await page.getByLabel("Event Title", { exact: true }).fill("Asha unsaved calendar edit");
    check(
      (
        await request(
          page,
          base,
          `/calendar/events/${event.id}`,
          { revision: event.revision, title: "Concurrent calendar edit" },
          "PATCH",
        )
      ).status === 200,
      `${tag}: another browser changes calendar event`,
    );
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page
      .getByRole("alert")
      .filter({ hasText: /This event changed/ })
      .waitFor();
    check(
      (await page.getByLabel("Event Title", { exact: true }).inputValue()) === "Asha unsaved calendar edit",
      `${tag}: stale calendar save retains the user's draft`,
    );
    await page.screenshot({ path: `${output}/${tag}-calendar-conflict.png`, fullPage: true });
    check(!errors.length && !external.length, `${tag}: no browser errors or external runtime requests`);
    await context.close();
  }
} catch (error) {
  for (const context of browser.contexts())
    for (const page of context.pages()) {
      await page.screenshot({ path: `${output}/failure.png`, fullPage: true }).catch(() => {});
      console.log((await page.locator("body").innerText()).slice(-4000));
    }
  throw error;
} finally {
  await browser.close();
}
