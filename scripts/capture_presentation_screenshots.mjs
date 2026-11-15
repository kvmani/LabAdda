import { createRequire } from "node:module";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "docs/presentation_assets");
const origin = "http://127.0.0.1:8000";
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";

const WORKSPACES = {
  NMRL: "8c216e09-1aa2-4b14-a0a6-be8743ea9389",
  SED: "002a6aff-4246-4b4d-9af3-96d2e18c1bfd",
  TFS: "75eabb23-14ff-4bd0-a7c6-7d5e807e091b",
  TEJ: "0adbb005-7fe7-43dd-809d-4bf5d2b3d94c",
  AKA: "840e1167-10f9-4bdb-ab46-dea2c94e6c01",
  Microscopy: "6c89f8e0-4e82-47c0-8bc5-e217e67b3b80",
};

async function capture() {
  console.log("Launching Edge browser via Playwright...");
  const browser = await chromium.launch({
    channel: "msedge",
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1.5, // Crisp retina-quality screenshots for presentation
  });

  const page = await context.newPage();

  async function login(username) {
    console.log(`Logging in as ${username}...`);
    await page.goto(`${origin}/login`);
    await page.waitForLoadState("networkidle");
    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
  }

  async function logout() {
    try {
      const menuBtn = page.getByRole("button", { name: /^Account menu for / });
      if (await menuBtn.isVisible()) {
        await menuBtn.click();
        await page.waitForTimeout(300);
        const signOut = page.getByRole("menuitem", { name: /Sign out/i });
        if (await signOut.isVisible()) {
          await signOut.click();
          await page.waitForLoadState("networkidle");
          await page.waitForTimeout(500);
        }
      }
    } catch (e) {
      // Clear cookies if menu logout fails
      await context.clearCookies();
    }
  }

  try {
    // 1. Capture Login Screen
    console.log("Capturing 01_login_screen.png...");
    await page.goto(`${origin}/login`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(outDir, "01_login_screen.png"), fullPage: false });

    // 2. Login as Bharat Kulkarni (Principal Scientist, Tejas Lead)
    await login("bharat");

    // Capture My Day / Dashboard
    console.log("Capturing 02_researcher_dashboard_my_day.png...");
    await page.goto(`${origin}/today`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(outDir, "02_researcher_dashboard_my_day.png") });

    // 3. Division Noticeboard (Surface Engineering Division)
    console.log("Capturing 03_division_noticeboard.png...");
    await page.goto(`${origin}/w/${WORKSPACES.SED}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(outDir, "03_division_noticeboard.png") });

    // 4. Collaborative Live Whiteboard (Project Tejas)
    console.log("Capturing 04_collaborative_live_whiteboard.png...");
    await page.goto(`${origin}/w/${WORKSPACES.TEJ}/board`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(outDir, "04_collaborative_live_whiteboard.png") });

    // 5. Project Group Chat & Threads (Project Tejas)
    console.log("Capturing 05_project_group_chat.png...");
    await page.goto(`${origin}/w/${WORKSPACES.TEJ}/chat`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(outDir, "05_project_group_chat.png") });

    // 6. Research Tasks Workflow (Project Tejas)
    console.log("Capturing 06_research_tasks_workflow.png...");
    await page.goto(`${origin}/w/${WORKSPACES.TEJ}/tasks`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(outDir, "06_research_tasks_workflow.png") });

    // 7. Personal Notes & Productivity
    console.log("Capturing 07_personal_notes_scratchpad.png...");
    await page.goto(`${origin}/notes`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000);
    await page.screenshot({ path: join(outDir, "07_personal_notes_scratchpad.png") });

    // 8. Organisation Chart
    console.log("Capturing 08_organisation_chart.png...");
    await page.goto(`${origin}/admin/org`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(outDir, "08_organisation_chart.png") });

    // Logout Bharat
    await logout();

    // 9. Login as Dr. Deepa Nair (Division Head & Unit Administrator)
    await login("deepa");
    console.log("Capturing 09_unit_administration_console.png...");
    await page.goto(`${origin}/admin/people`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(outDir, "09_unit_administration_console.png") });

    // Logout Deepa
    await logout();

    // 10. Login as Site Administrator
    await login("admin");
    console.log("Capturing 10_site_administration_health.png...");
    await page.goto(`${origin}/admin/health`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(outDir, "10_site_administration_health.png") });

    console.log("Capturing 11_site_admin_overview.png...");
    await page.goto(`${origin}/admin/overview`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(outDir, "11_site_admin_overview.png") });

    console.log("Capturing 12_audit_trail_explorer.png...");
    await page.goto(`${origin}/admin/audit`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.screenshot({ path: join(outDir, "12_audit_trail_explorer.png") });

    console.log("All screenshots captured successfully!");
  } catch (err) {
    console.error("Screenshot capture failed:", err);
  } finally {
    await browser.close();
  }
}

capture();
