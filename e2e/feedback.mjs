// Pilot Feedback button: a member sends a message with a pasted screenshot; the administrator sees it in the
// Feedback table, opens it, and marks it resolved. Runs at / and /labadda-staging with axe at two widths.
// Usage: node e2e/feedback.mjs [out-dir]
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-feedback";
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

async function pasteScreenshot(page) {
  await page.getByLabel(/^Your message/).focus();
  await page.evaluate(async () => {
    const canvas = document.createElement("canvas");
    canvas.width = 60;
    canvas.height = 40;
    const context = canvas.getContext("2d");
    context.fillStyle = "#1565c0";
    context.fillRect(0, 0, 60, 40);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    const transfer = new DataTransfer();
    transfer.items.add(new File([blob], "image.png", { type: "image/png" }));
    document.activeElement.dispatchEvent(
      new ClipboardEvent("paste", { clipboardData: transfer, bubbles: true, cancelable: true }),
    );
  });
}

async function run(base) {
  const label = base || "root";
  const text = `Pressure sensor graph is blank on the Tejas board (${label})`;
  const member = await login(base, "bharat");
  const page = member.page;
  await page.getByRole("button", { name: "Feedback", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Send feedback" });
  await dialog.waitFor();
  check(
    await dialog.getByText("Administrators will read this message and its attachments").isVisible(),
    label + " the form says administrators will read it",
  );
  await dialog.getByText("bharat", { exact: true }).waitFor();
  check(await dialog.getByText("Software version").isVisible(), label + " the form shows what is sent");
  await dialog.getByRole("button", { name: "Send to the administrators" }).click();
  check(await dialog.getByRole("alert").isVisible(), label + " an empty message is refused");
  await dialog.getByLabel(/^Your message/).fill(text);
  await pasteScreenshot(page);
  await dialog
    .getByRole("list", { name: "Files to send" })
    .getByText(/screenshot-\d+\.png/)
    .waitFor();
  check(true, label + " a pasted picture is listed");
  await audit(page, 1400, label + " dialog");
  await audit(page, 390, label + " dialog");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-dialog.png` });
  await dialog.getByRole("button", { name: "Send to the administrators" }).click();
  await page.getByText("Sent to the administrators").waitFor();
  check(true, label + " the person sees it was sent");
  await page.getByRole("button", { name: "Close", exact: true }).first().click();
  await member.context.close();

  const admin = await login(base, "admin");
  const adminPage = admin.page;
  await adminPage.goto(origin + base + "/admin/feedback");
  await adminPage.getByRole("heading", { name: "Feedback", exact: true }).waitFor();
  await adminPage.getByText("E-mail not configured", { exact: false }).first().waitFor();
  check(true, label + " the page says e-mail is not configured");
  const row = adminPage.locator("tbody tr", { hasText: "bharat" }).first();
  await row.waitFor();
  check((await row.innerText()).includes("1"), label + " the row shows one attached file");
  await audit(adminPage, 1400, label + " table");
  await row.getByRole("button", { name: /Open feedback from bharat/ }).click();
  const drawer = adminPage.getByRole("dialog", { name: "Feedback" });
  await drawer.getByText(text).waitFor();
  const image = drawer.getByRole("img", { name: /screenshot-\d+\.png/ });
  await image.waitFor();
  check(
    await image.evaluate((node) => node.complete && node.naturalWidth > 0),
    label + " the screenshot preview loads",
  );
  await audit(adminPage, 1400, label + " detail");
  await audit(adminPage, 390, label + " detail");
  await adminPage.screenshot({ path: `${output}/${base ? "prefix" : "root"}-admin.png` });
  await drawer.getByLabel("Status", { exact: true }).selectOption("resolved");
  await drawer.getByLabel("Administrator note").fill("Re-zeroed the sensor.");
  await drawer.getByRole("button", { name: "Save status and note" }).click();
  await drawer.getByText("Saved.").waitFor();
  await drawer.getByRole("button", { name: "Close panel" }).click();
  await adminPage.locator("tbody tr", { hasText: "Resolved" }).first().waitFor();
  check(true, label + " the list shows the message as resolved");
  await admin.context.close();
}

for (const base of ["", "/labadda-staging"]) await run(base);
await browser.close();
console.log(`feedback: ${checks} checks passed`);
