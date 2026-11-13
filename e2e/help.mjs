// H1 browser check: the help centre works offline from the server, searches locally, opens beside
// the work, prints cleanly and passes axe at desktop and phone width. Usage: node e2e/help.mjs [out-dir]
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080",
  out = process.argv[2] ?? "/tmp/help-check",
  axeSource = require.resolve("../frontend/node_modules/axe-core/axe.min.js");
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
const check = (condition, label) => {
  assert.ok(condition, label);
  checks++;
  console.log("PASS " + label);
};

async function signIn(base, username) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } }),
    page = await context.newPage(),
    problems = [],
    outsideRequests = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("request", (request) => {
    if (!request.url().startsWith(origin) && !request.url().startsWith("data:"))
      outsideRequests.push(request.url());
  });
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { context, page, problems, outsideRequests };
}

async function audit(page, width, label) {
  await page.setViewportSize({ width, height: 1000 });
  await page.addScriptTag({ path: axeSource });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((violation) => violation.id),
  );
  check(violations.length === 0, `${label} has no accessibility violations at ${width}px ${violations}`);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}px without sideways scrolling`,
  );
}

async function checkHome(member, admin, base) {
  const page = member.page;
  await page.goto(origin + base + "/help");
  await page.getByRole("heading", { level: 1, name: "Help", exact: true }).waitFor();
  const shelves = await page.locator("#main").getByRole("heading", { level: 2 }).allTextContents();
  check(
    [...shelves.slice(0, 4)].sort().join("|") ===
      "Administering LabAdda|Looking after a workspace|Running the server|Using LabAdda",
    base + " help home shows the four shelves",
  );
  check(
    shelves[0] === "Looking after a workspace",
    base + " a steward sees their own shelf first: " + shelves,
  );
  check(shelves[4] === "Words and fixes", base + " help home shows the glossary shelf");
  await page.getByRole("link", { name: "Signing in for the first time", exact: true }).waitFor();
  await page.screenshot({ path: `${out}/${base.replace("/", "") || "root"}-home.png`, fullPage: true });
  await audit(page, 1400, base + " help home");
  await audit(page, 390, base + " help home");
  await page.setViewportSize({ width: 1400, height: 1000 });

  await admin.page.goto(origin + base + "/help");
  await admin.page.getByRole("heading", { level: 2, name: "Administering LabAdda" }).waitFor();
  const first = (await admin.page.locator("#main").getByRole("heading", { level: 2 }).allTextContents())[0];
  check(first === "Administering LabAdda", base + " an administrator sees their own shelf first");
}

async function checkSearch(member, base) {
  const page = member.page;
  await page.goto(origin + base + "/help");
  const box = page.getByRole("searchbox", { name: "Search help" });
  await box.fill("password");
  await page.getByRole("link", { name: "Glossary", exact: true }).waitFor({ state: "detached" });
  check(
    await page.getByRole("link", { name: "Signing in for the first time", exact: true }).isVisible(),
    base + " search finds pages by their words and hides the rest",
  );
  await box.fill("zzzz nothing");
  await page.getByText("No guides match your search").waitFor();
  check(true, base + " search with no match says so in plain words");
  await box.fill("workspace");
  await page.getByRole("link", { name: "Glossary", exact: true }).waitFor();
  check(true, base + " search matches summaries");
}

async function checkPage(member, base) {
  const page = member.page;
  await page.goto(origin + base + "/help/using/signing-in");
  await page.getByRole("heading", { level: 1, name: "Signing in for the first time" }).waitFor();
  await page.locator(".help-article").waitFor();
  check(await page.getByText("Activate account").first().isVisible(), base + " help page shows its steps");
  check(
    (await page.locator(".help-article strong").count()) > 0,
    base + " on-screen labels are shown in bold",
  );
  await page.getByRole("link", { name: "Finding your way around", exact: true }).click();
  await page.getByRole("heading", { level: 1, name: "Finding your way around" }).waitFor();
  check(
    page.url().endsWith(base + "/help/using/finding-your-way"),
    base + " links between pages stay in the app",
  );
  await page.screenshot({ path: `${out}/${base.replace("/", "") || "root"}-page.png`, fullPage: true });
  await audit(page, 1400, base + " help page");
  await audit(page, 390, base + " help page");
  await page.setViewportSize({ width: 1400, height: 1000 });
  await page.emulateMedia({ media: "print" });
  check(
    await page.locator(".shell-topbar").evaluate((element) => getComputedStyle(element).display === "none"),
    base + " print layout hides the navigation",
  );
  await page.emulateMedia({ media: "screen" });
  await page.goto(origin + base + "/help/using/does-not-exist");
  await page.getByText("That help page does not exist").waitFor();
  check(true, base + " an unknown help page says so and offers a way back");
}

async function checkDrawer(member, base) {
  const page = member.page;
  await page.goto(origin + base + "/today");
  await page.getByRole("button", { name: "Help with this page", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Reading My day" });
  await drawer.waitFor();
  await drawer.getByText("Active work and deadlines").first().waitFor();
  check(
    await page.getByRole("heading", { level: 1, name: "My day" }).isVisible(),
    base + " the screen stays visible beside the help drawer",
  );
  await page.screenshot({ path: `${out}/${base.replace("/", "") || "root"}-drawer.png` });
  await audit(page, 1400, base + " help drawer");
  await audit(page, 390, base + " help drawer");
  await page.setViewportSize({ width: 1400, height: 1000 });
  await page.keyboard.press("Escape");
  await drawer.waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Help with this page", exact: true }).click();
  await page.getByRole("button", { name: "Open the full guide", exact: true }).click();
  await page.getByRole("heading", { level: 1, name: "Reading My day" }).waitFor();
  check(page.url().endsWith(base + "/help/using/my-day"), base + " the drawer opens the full guide");
  await page.goto(origin + base + "/no-such-screen"); // /notes has its own help page now
  await page.getByRole("heading", { level: 1 }).first().waitFor();
  check(
    (await page.getByRole("button", { name: "Help with this page" }).count()) === 0,
    base + " a screen with no help page shows no help control",
  );
}

try {
  for (const base of ["", "/labadda-staging"]) {
    const member = await signIn(base, "ben"),
      admin = await signIn(base, "admin");
    await checkHome(member, admin, base);
    await checkSearch(member, base);
    await checkPage(member, base);
    await checkDrawer(member, base);
    check(member.problems.length === 0, base + " help raised no page errors " + member.problems);
    check(
      member.outsideRequests.length === 0,
      base + " help made no request outside the server " + member.outsideRequests,
    );
    await member.context.close();
    await admin.context.close();
  }
  console.log(`help: ${checks} checks passed`);
} finally {
  await browser.close();
}
