import { createRequire } from "node:module";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "docs/whiteboard_assets");
const origin = "http://127.0.0.1:8000";
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const TEJAS_WORKSPACE = "0adbb005-7fe7-43dd-809d-4bf5d2b3d94c";

async function main() {
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

  // 1. Sign in as Bharat (Project Lead & Scientist)
  console.log("Signing in as Dr. Bharat Kulkarni...");
  await page.goto(`${origin}/login`);
  await page.waitForLoadState("networkidle");
  await page.getByLabel("Username").fill("bharat");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1000);

  // 2. Navigate to Project Tejas Whiteboard
  console.log("Navigating to Project Tejas Whiteboard...");
  await page.goto(`${origin}/w/${TEJAS_WORKSPACE}/board`);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);

  // 3. Clear board via restore to revision 0 for a clean team collaboration view
  console.log("Cleaning board for pristine creative shapes layout...");
  await page.evaluate(async ({ workspaceId }) => {
    const sessionRes = await fetch("/api/v1/auth/session");
    const sessionData = await sessionRes.json();
    const csrfToken = sessionData.csrf_token;

    // Reset board to revision 0
    await fetch(`/api/v1/workspaces/${workspaceId}/board/restore`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ revision: 0, reason: "Whiteboard creative shapes showcase" }),
    });
  }, { workspaceId: TEJAS_WORKSPACE });

  await page.waitForTimeout(1000);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);

  // 4. Populate with diverse creative sticky notes and schematic drawing
  console.log("Adding creative sticky notes across all 6 shapes...");
  const creativeNotes = [
    {
      shape: "rectangle",
      color: "#fff59d", // Classic Yellow
      text: "▭ PROTOCOL\nISO Class 5 Cleanroom\nSubstrate Sonication: 15 min",
      x: 60,
      y: 60,
    },
    {
      shape: "circle",
      color: "#b3e5fc", // Sky Blue
      text: "◯ TARGET SPEC\n99.995% Pure\nTi / Sc Target",
      x: 280,
      y: 45,
    },
    {
      shape: "hexagon",
      color: "#c8e6c9", // Mint Green
      text: "⬡ MATERIAL PHASE\nAnatase TiO2-x\nc = 2.958 Å",
      x: 470,
      y: 50,
    },
    {
      shape: "diamond",
      color: "#ffccbc", // Coral / Peach
      text: "◇ DECISION POINT\nAr:O2 = 5:1 Ratio\nTemp = 350°C",
      x: 670,
      y: 45,
    },
    {
      shape: "cloud",
      color: "#e1bee7", // Lavender
      text: "☁ HYPOTHESIS\nOxygen Vacancy Drift\nEnhanced Carrier Mobility",
      x: 100,
      y: 240,
    },
    {
      shape: "star",
      color: "#ffe082", // Amber / Gold
      text: "★ BREAKTHROUGH\nRun #104 Success!\nTransmittance >88%",
      x: 340,
      y: 220,
    },
  ];

  await page.evaluate(async ({ notes, workspaceId }) => {
    const sessionRes = await fetch("/api/v1/auth/session");
    const sessionData = await sessionRes.json();
    const csrfToken = sessionData.csrf_token;

    // Draw an ink flow arrow between steps
    const strokePoints = [
      [240, 110], [255, 110], [270, 110],
      [430, 110], [445, 110], [460, 110],
      [630, 110], [645, 110], [660, 110]
    ];
    await fetch(`/api/v1/workspaces/${workspaceId}/board/ops`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({
        op_id: "arrow-stroke-1",
        epoch: 2,
        type: "add",
        object_id: "stroke-flow-1",
        payload: {
          kind: "stroke",
          data: {
            points: [[240, 115], [250, 115], [265, 115], [260, 110], [265, 115], [260, 120]],
            color: "#1565c0",
            width: 3,
          },
        },
      }),
    });

    for (let i = 0; i < notes.length; i++) {
      const n = notes[i];
      const opId = `op-shape-${i}-${Date.now()}`;
      const objId = `shape-obj-${i}`;
      await fetch(`/api/v1/workspaces/${workspaceId}/board/ops`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({
          op_id: opId,
          epoch: 2,
          type: "add",
          object_id: objId,
          payload: {
            kind: "sticky",
            data: {
              x: n.x,
              y: n.y,
              text: n.text,
              color: n.color,
              shape: n.shape,
            },
          },
        }),
      });
    }
  }, { notes: creativeNotes, workspaceId: TEJAS_WORKSPACE });

  await page.waitForTimeout(1000);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);

  // Activate Sticky tool in UI to show the shape selector toolbar
  console.log("Activating Sticky tool to showcase the shape toolbar...");
  const stickyBtn = page.getByRole("button", { name: "🗒 Sticky" });
  if (await stickyBtn.isVisible()) {
    await stickyBtn.click();
    await page.waitForTimeout(500);
  }

  // 5. Capture AFTER screenshot showing whiteboard with new creative sticky notes
  console.log("Capturing 02_whiteboard_after_creative_shapes.png...");
  await page.screenshot({
    path: join(outDir, "02_whiteboard_after_creative_shapes.png"),
    fullPage: false,
  });

  // 6. Capture focused toolbar detail
  console.log("Capturing 03_sticky_shapes_toolbar_detail.png...");
  const toolbar = page.locator(".toolbar");
  if (await toolbar.isVisible()) {
    await toolbar.screenshot({
      path: join(outDir, "03_sticky_shapes_toolbar_detail.png"),
    });
  }

  console.log("All screenshots captured successfully in docs/whiteboard_assets!");
  await browser.close();
}

main().catch((err) => {
  console.error("Error capturing whiteboard screenshots:", err);
  process.exit(1);
});
