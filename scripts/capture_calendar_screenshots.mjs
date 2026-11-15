import { createRequire } from "node:module";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(resolve("e2e/package.json"));
const { chromium } = require("playwright");

const artifactDir = "C:/Users/kvman/.gemini/antigravity/brain/5ec2c235-285e-48d6-86ab-d70ffe00ec45";
const origin = "http://127.0.0.1:8000";
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";

async function run() {
  console.log("Launching Edge browser via Playwright...");
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.5,
  });

  const page = await context.newPage();

  console.log("Signing in as bharat...");
  await page.goto(`${origin}/login`);
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Username").fill("bharat");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);

  console.log("Navigating to /calendar...");
  await page.goto(`${origin}/calendar`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);

  // 1. Month View
  console.log("Capturing Month View...");
  await page.screenshot({
    path: join(artifactDir, "calendar_month_view.png"),
    fullPage: false,
  });

  // 2. Week View
  console.log("Switching to Week View...");
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await page.waitForTimeout(800);
  await page.evaluate(() => {
    window.scrollTo(0, 420);
  });
  await page.waitForTimeout(400);
  await page.screenshot({
    path: join(artifactDir, "calendar_week_view.png"),
    fullPage: false,
  });

  // 3. Day View
  console.log("Switching to Day View...");
  await page.getByRole("button", { name: "Day", exact: true }).click();
  await page.waitForTimeout(500);
  // Navigate to Tuesday Nov 17
  await page.locator('.cal-topbar .cal-nav-arrow[title="Next"]').click();
  await page.waitForTimeout(300);
  await page.locator('.cal-topbar .cal-nav-arrow[title="Next"]').click();
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    window.scrollTo(0, 300);
  });
  await page.waitForTimeout(400);
  await page.screenshot({
    path: join(artifactDir, "calendar_day_view.png"),
    fullPage: false,
  });
  // Reset back to today
  await page.getByRole("button", { name: "Today", exact: true }).click();
  await page.waitForTimeout(500);

  // 4. Schedule / Agenda View
  console.log("Switching to Schedule / Agenda View...");
  await page.getByRole("button", { name: "Schedule", exact: true }).click();
  await page.waitForTimeout(800);
  await page.screenshot({
    path: join(artifactDir, "calendar_agenda_view.png"),
    fullPage: false,
  });

  // 5. Create Event Modal
  console.log("Opening Create Event Dialog...");
  await page.getByRole("button", { name: "Month", exact: true }).click();
  await page.waitForTimeout(500);
  await page.locator(".cal-btn-create").click();
  await page.waitForTimeout(800);
  await page.screenshot({
    path: join(artifactDir, "calendar_create_modal.png"),
    fullPage: false,
  });

  console.log("All calendar screenshots captured successfully!");
  await browser.close();
}

run().catch((err) => {
  console.error("Error capturing screenshots:", err);
  process.exit(1);
});
