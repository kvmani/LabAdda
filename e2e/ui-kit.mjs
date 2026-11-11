// U1 component gallery: axe-core WCAG 2.1 A/AA, themes, phone width and dialog focus, on the
// Vite dev server (the gallery is not part of production builds).
//   node e2e/ui-kit.mjs [screenshot-dir]
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const AXE = require.resolve(join(ROOT, "frontend/node_modules/axe-core/axe.min.js"));
const PORT = Number(process.env.LABADDA_UI_KIT_PORT ?? 5199);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const OUT = process.argv[2] ?? "/tmp/labadda-ui-kit";
const DARK_PAGE = "rgb(15, 20, 25)";
const LIGHT_PAGE = "rgb(244, 245, 247)";

let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  checks += 1;
  console.log("PASS  " + label);
}

function startDevServer() {
  const server = spawn(
    join(ROOT, "frontend/node_modules/.bin/vite"),
    ["--port", String(PORT), "--strictPort", "--host", "127.0.0.1"],
    { cwd: join(ROOT, "frontend"), detached: true, stdio: "ignore" },
  );
  return server;
}

async function waitForServer(deadlineSeconds) {
  const deadline = Date.now() + deadlineSeconds * 1000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${ORIGIN}/_ui`);
      if (response.ok) return;
    } catch {
      // Not listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Vite dev server did not start on ${ORIGIN} within ${deadlineSeconds} s`);
}

async function axeViolations(page) {
  await page.addScriptTag({ path: AXE });
  return page.evaluate(async () => {
    const result = await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    });
    return result.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(" ")),
    }));
  });
}

async function openGallery(page, theme) {
  await page.goto(`${ORIGIN}/_ui`);
  await page.evaluate((choice) => window.localStorage.setItem("labadda.theme", choice), theme);
  await page.reload();
  await page.getByRole("heading", { level: 1, name: "Component gallery" }).waitFor();
}

const server = startDevServer();
const browser = await chromium.launch({ executablePath: process.env.LABADDA_CHROMIUM });
try {
  mkdirSync(OUT, { recursive: true });
  await waitForServer(60);
  for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => message.type() === "error" && errors.push(message.text()));
    await openGallery(page, theme);

    const background = await page.evaluate(
      () => getComputedStyle(document.querySelector(".gallery")).backgroundColor,
    );
    check(
      background === (theme === "dark" ? DARK_PAGE : LIGHT_PAGE),
      `${theme}: theme is applied (${background})`,
    );

    for (const width of [1400, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      const violations = await axeViolations(page);
      check(
        violations.length === 0,
        `${theme} ${width}px: no WCAG 2.1 A/AA violations ${JSON.stringify(violations)}`,
      );
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      check(overflow <= 0, `${theme} ${width}px: page does not scroll sideways (${overflow}px)`);
      await page.screenshot({ path: `${OUT}/gallery-${theme}-${width}.png`, fullPage: true });
    }

    await page.setViewportSize({ width: 1400, height: 1000 });
    const opener = page.getByRole("button", { name: "Open confirmation", exact: true });
    await opener.click();
    const dialog = page.getByRole("dialog", { name: "Retire Dana Iyer?" });
    await dialog.waitFor();
    const focusedLabel = await page.evaluate(() => document.activeElement?.getAttribute("aria-describedby"));
    check(Boolean(focusedLabel), `${theme}: focus moves to the reason field in the confirmation`);
    const dialogViolations = await axeViolations(page);
    check(
      dialogViolations.length === 0,
      `${theme}: open confirmation has no violations ${JSON.stringify(dialogViolations)}`,
    );
    await page.screenshot({ path: `${OUT}/confirm-${theme}.png` });
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    check(
      await opener.evaluate((element) => element === document.activeElement),
      `${theme}: Escape closes the confirmation and returns focus`,
    );
    check(errors.length === 0, `${theme}: no console errors ${JSON.stringify(errors)}`);
    await context.close();
  }
  console.log(`${checks} ui-kit browser checks passed. Screenshots: ${OUT}`);
} finally {
  await browser.close();
  process.kill(-server.pid, "SIGTERM");
}
