// T13 accessibility audit: axe-core (WCAG 2.1 A/AA rules) plus keyboard and narrow-screen checks
// on the main desktop, mobile and touch-panel views, at root and prefix.
// Run against a fresh disposable `scripts/proxy-stack.sh start` (HTTP) stack.
// Automated rules catch a subset of WCAG issues; a manual screen-reader and visual review is still required.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const AXE = require.resolve("../frontend/node_modules/axe-core/axe.min.js");
const origin = process.argv[2] ?? "http://127.0.0.1:8080";
if (!["127.0.0.1", "localhost"].includes(new URL(origin).hostname))
  throw Error("Use a local disposable test stack");
const out = process.argv[3] ?? "/tmp/labadda-accessibility";
mkdirSync(out, { recursive: true });
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const browser = await chromium.launch(
  process.env.LABADDA_CHROMIUM ? { executablePath: process.env.LABADDA_CHROMIUM } : {},
);
const findings = [];
const blockingPages = [];
let checks = 0;
function check(value, text) {
  assert.ok(value, text);
  checks++;
  console.log("PASS " + text);
}

async function audit(page, label) {
  await page.addScriptTag({ path: AXE });
  const result = await page.evaluate(() =>
    window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      resultTypes: ["violations"],
    }),
  );
  const violations = result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.length,
    targets: v.nodes.slice(0, 3).map((n) => n.target.join(" ")),
  }));
  findings.push({ page: label, violations });
  const blocking = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  for (const v of violations) console.log(`  ${v.impact} ${v.id} (${v.nodes}) ${v.targets.join(" | ")}`);
  // Record and continue so one run reports every page; the run fails at the end if anything blocks.
  if (blocking.length) blockingPages.push(label);
  else {
    checks++;
    console.log(`PASS ${label}: no serious or critical WCAG 2.1 A/AA violations`);
  }
  return violations;
}

async function signIn(ctx, base, name) {
  const page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return page;
}

async function keyboard(page, label) {
  await page.keyboard.press("Tab");
  const first = await page.evaluate(() => ({
    text: document.activeElement?.textContent?.trim(),
    href: document.activeElement?.getAttribute("href"),
  }));
  check(first.text === "Skip to main content", `${label}: first Tab reaches the skip link`);
  await page.keyboard.press("Enter");
  check(
    await page.evaluate(() => document.activeElement?.id === "main"),
    `${label}: skip link moves focus to the main region`,
  );
  // Every focused control shows a visible indicator (outline or box-shadow).
  const unindicated = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    const state = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const style = getComputedStyle(el);
      const visible =
        (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== "none";
      return {
        visible,
        name: (el.getAttribute("aria-label") || el.textContent || el.tagName).trim().slice(0, 40),
      };
    });
    if (state && !state.visible) unindicated.push(state.name);
  }
  check(
    unindicated.length === 0,
    `${label}: keyboard focus is visible on every control reached (${unindicated.join(", ") || "all visible"})`,
  );
}

async function noHorizontalScroll(page, label) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(overflow <= 1, `${label}: no horizontal page scroll at phone width (overflow ${overflow}px)`);
}

try {
  for (const base of ["", "/labadda-staging"]) {
    const tag = base || "root";
    const desktop = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const anon = await desktop.newPage();
    await anon.goto(origin + base + "/");
    await anon.getByLabel("Username").waitFor();
    await audit(anon, `${tag} sign-in`);
    await anon.close();

    const page = await signIn(desktop, base, "asha");
    const spaces = (await (await desktop.request.get(origin + base + "/api/v1/workspaces")).json())
      .workspaces;
    const section = spaces.find((w) => w.name === "Thin Films Section").id;
    const group = spaces.find((w) => w.kind === "group")?.id ?? section;
    await page.goto(origin + base + `/w/${section}/noticeboard`);
    await page.getByLabel("Message").fill("Accessibility audit post with a due date");
    await page.getByRole("button", { name: "Post", exact: true }).click();
    await page.getByRole("status").filter({ hasText: "Posted" }).waitFor();
    await page.reload();
    await page.locator(".post").first().waitFor();
    await keyboard(page, `${tag} noticeboard`);
    await audit(page, `${tag} noticeboard`);
    for (const [path, ready, label] of [
      [`/w/${section}/board`, ".canvas", "whiteboard"],
      [`/w/${section}/chat`, "form[aria-label='Send chat message']", "chat"],
      [`/w/${group}/members`, "table", "group members"],
      ["/notes", "form", "my notes"],
      ["/usage", "table", "storage usage"],
      ["/groups/new", "form", "new group"],
    ]) {
      await page.goto(origin + base + path);
      await page.locator(ready).first().waitFor();
      await audit(page, `${tag} ${label}`);
    }
    await page.screenshot({ path: `${out}/${tag.replace("/", "")}-desktop-usage.png`, fullPage: true });
    await desktop.close();

    const adminCtx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const admin = await signIn(adminCtx, base, "admin");
    await admin.goto(origin + base + "/admin");
    await admin.getByRole("heading", { name: "Administration" }).waitFor();
    await audit(admin, `${tag} administration`);
    await adminCtx.close();

    const tablet = await browser.newContext({ viewport: { width: 1024, height: 768 } });
    const tabletPage = await signIn(tablet, base, "ben");
    await tabletPage.goto(origin + base + `/w/${section}/noticeboard`);
    await tabletPage.locator(".post").first().waitFor();
    await audit(tabletPage, `${tag} tablet noticeboard`);
    await noHorizontalScroll(tabletPage, `${tag} tablet noticeboard`);
    await tabletPage.screenshot({
      path: `${out}/${tag.replace("/", "")}-tablet-noticeboard.png`,
      fullPage: true,
    });
    await tablet.close();

    const phone = await browser.newContext({
      viewport: { width: 390, height: 844 },
      hasTouch: true,
      isMobile: true,
    });
    const mobile = await signIn(phone, base, "ben");
    await mobile.goto(origin + base + `/w/${section}/noticeboard`);
    await mobile.locator(".post").first().waitFor();
    await audit(mobile, `${tag} mobile noticeboard`);
    await noHorizontalScroll(mobile, `${tag} mobile noticeboard`);
    await mobile.goto(origin + base + "/usage");
    await mobile.locator("table").first().waitFor();
    await noHorizontalScroll(mobile, `${tag} mobile usage`);
    await mobile.screenshot({
      path: `${out}/${tag.replace("/", "")}-mobile-noticeboard.png`,
      fullPage: true,
    });
    await phone.close();

    // Touch panel: pairing screen and board view.
    const pairCtx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const pairer = await signIn(pairCtx, base, "ben");
    const code = (
      await (
        await pairCtx.request.post(origin + base + "/api/v1/panel/pairings", {
          data: { workspace_id: section },
          headers: {
            "X-CSRF-Token": (await (await pairCtx.request.get(origin + base + "/api/v1/auth/session")).json())
              .csrf_token,
          },
        })
      ).json()
    ).code;
    const kiosk = await browser.newContext({ viewport: { width: 1280, height: 800 }, hasTouch: true });
    const panel = await kiosk.newPage();
    await panel.goto(origin + base + "/panel");
    await panel.getByLabel("Panel code").waitFor();
    await audit(panel, `${tag} panel pairing`);
    await panel.getByLabel("Panel code").fill(code);
    await panel.getByRole("button", { name: "Open board" }).click();
    await panel.getByRole("button", { name: "End session" }).waitFor();
    await audit(panel, `${tag} panel board`);
    await panel.getByRole("button", { name: "End session" }).click();
    await kiosk.close();
    await pairer.close();
    await pairCtx.close();
  }
  writeFileSync(`${out}/axe-findings.json`, JSON.stringify(findings, null, 2));
  const remaining = findings.flatMap((f) => f.violations.map((v) => `${f.page}: ${v.impact} ${v.id}`));
  console.log(
    `${checks} accessibility checks passed. Findings: ${remaining.length ? remaining.join("; ") : "none"}`,
  );
  assert.equal(blockingPages.length, 0, `Serious or critical violations on: ${blockingPages.join(", ")}`);
} finally {
  await browser.close();
}
