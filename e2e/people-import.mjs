// P6 staff list import: upload, report, selection, review, apply, slips, bulk move; root and prefix.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-people-import";
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
const FILE =
  "employee_no,username,display_name,designation,unit_code,role,status,effective_on\n" +
  "NM-701,imp.one,Imani One,Research Officer,CS,member,,2026-12-01\n" +
  "NM-702,imp.two,Ira Two,,TFS,steward,,\n" +
  ",imp.bad,Bad Row,,NOPE,,,\n";

async function importList(page, base) {
  await page.goto(origin + base + "/admin/people");
  await page.getByRole("button", { name: "Import staff list", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Import a staff list", exact: true });
  await dialog.getByLabel("Staff list CSV file").setInputFiles({
    name: "people.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("x"),
  });
  check(
    await dialog.getByRole("alert").getByText(/\.csv/).isVisible(),
    base + " non-CSV refused in the browser",
  );
  await dialog.getByLabel("Staff list CSV file").setInputFiles({
    name: "people.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(FILE),
  });
  const report = dialog.getByRole("region", { name: "Import report" });
  await report.waitFor();
  check(await report.getByText("No open unit has the code NOPE.").isVisible(), base + " bad row explained");
  check(
    (await report.getByRole("checkbox", { name: /Line 4/ }).count()) === 0,
    base + " bad row cannot be selected",
  );
  check(
    await report.getByText(/people are not in the file and will not be changed/).isVisible(),
    base + " absent people listed, not changed",
  );
  await page.screenshot({ path: `${output}/report${base.replaceAll("/", "-") || "-root"}.png` });
  await audit(page, 1400, base + " import report");
  await dialog.getByRole("checkbox", { name: "Line 3: Ira Two" }).uncheck();
  await dialog.getByRole("button", { name: "Review 1 selected row", exact: true }).click();
  const review = page.getByRole("dialog", { name: "Review the staff list changes" });
  await review.getByText("Create an invited account for Imani One (imp.one)").waitFor();
  await review.getByLabel(/^Reason for this change/).fill("Autumn joiners");
  await review.getByRole("button", { name: "Apply 1 change", exact: true }).click();
  const slip = review.getByRole("region", { name: "Activation slip for Imani One" });
  await slip.waitFor();
  check(
    ((await slip.locator(".people-slip__code").textContent()) ?? "").trim().length >= 10,
    base + " activation slip shows a code",
  );
  await page.screenshot({ path: `${output}/slips${base.replaceAll("/", "-") || "-root"}.png` });
  await review.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("button", { name: "View profile for Imani One" }).waitFor();
  check(true, base + " imported person appears in the list");
  check(
    (await page.getByRole("button", { name: "View profile for Ira Two" }).count()) === 0,
    base + " unselected row was not applied",
  );
}
async function bulkSuspend(page, base) {
  await page.getByRole("checkbox", { name: "Select Imani One" }).check();
  const bar = page.getByRole("group", { name: "Actions for selected people" });
  await bar.getByRole("button", { name: "Review suspension", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Suspend the selected people" });
  await dialog.getByLabel(/^Reason for this change/).fill("Offer withdrawn");
  await dialog.getByRole("button", { name: "Apply 1 change", exact: true }).click();
  await dialog.getByText("1 change was applied.").waitFor();
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  check(true, base + " bulk suspension applied");
}
async function denied(base) {
  const bharat = await login(base, "bharat");
  try {
    const endpoint = origin + base + "/api/v1";
    const session = await (await bharat.context.request.get(endpoint + "/auth/session")).json();
    const post = await bharat.context.request.post(endpoint + "/admin/changes/import/preview", {
      headers: { "X-CSRF-Token": session.csrf_token, "Content-Type": "text/csv" },
      data: FILE,
    });
    check(post.status() === 403, base + " member cannot use the import API");
  } finally {
    await bharat.context.close();
  }
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await importList(admin.page, base);
      await bulkSuspend(admin.page, base);
    } finally {
      await admin.context.close();
    }
    await denied(base);
  }
  console.log(`${checks} people import browser checks passed`);
} finally {
  await browser.close();
}
