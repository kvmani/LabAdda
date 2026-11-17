// P6 browser check: a signed-out visitor applies to join from the sign-in page, sees only
// organisation units (never private groups or projects), gets the receipt, and an administrator
// then finds the pending application. Runs at the root and the prefixed instance.
// Usage: node e2e/join-requests.mjs [out-dir]     Requires fresh proxy-stack fixtures.
import { mkdirSync } from "node:fs";
import { axeViolations, bases, call, hasNoSideScroll, origin, startHarness } from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/labadda-join-requests";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { browser, check, login } = harness;
const privateNames = ["Microscopy Journal Club", "Project Tejas"];

async function apply(base, username) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(origin + base + "/");
  await page.getByRole("link", { name: /Apply to join LabAdda/ }).click();
  await page.waitForURL(origin + base + "/join");
  const unitSelect = page.getByLabel(/Home Division or Section/);
  await unitSelect.locator("option").nth(1).waitFor({ state: "attached" });
  const options = await unitSelect.locator("option").allTextContents();
  check(
    !options.some((text) => privateNames.some((name) => text.includes(name))),
    base + ": unit list hides private groups and projects",
  );
  for (const width of [1400, 390]) {
    await page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(page);
    check(violations.length === 0, base + ": join form accessibility " + width + " " + violations.join(","));
    check(await hasNoSideScroll(page), base + ": join form no overflow " + width);
  }
  await page.setViewportSize({ width: 1400, height: 1100 });
  await page.getByLabel(/Full Name/).fill("Kavya Rao");
  await page.getByLabel(/Preferred User ID/).fill(username);
  await page.locator("#employee-no").fill(`EMP-${username}`);
  await page.locator("#email").fill(`${username}@domain.in`);
  await page.locator("#designation").fill("Scientist B");
  await unitSelect.selectOption({ index: 0 });
  await page.getByLabel(/purely voluntary/).check();
  await page.getByRole("button", { name: "Submit Voluntary Application" }).click();
  await page.getByRole("heading", { name: "Application Submitted Successfully!" }).waitFor();
  await page.screenshot({ path: `${outputDir}/${base ? "prefix" : "root"}-join-receipt.png` });
  check(errors.length === 0, base + ": join page has no script errors " + errors.join(" | "));
  await context.close();
}

try {
  for (const base of bases) {
    const username = `kavya${base ? "p" : "r"}${Date.now() % 100000}`;
    await apply(base, username);
    const admin = await login(base, "admin");
    const pending = await call(admin, "/admin/join-requests?status=pending");
    check(
      pending.requests.some((item) => item.username === username),
      base + ": administrator sees the pending application",
    );
    await admin.ctx.close();
  }
  console.log(`join-requests: ${harness.checks()} checks passed`);
} finally {
  await harness.close();
}
