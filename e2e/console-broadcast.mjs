// AD-11 Broadcast: admin adds, edits, orders, turns off and deletes messages; everyone signed in sees the
// scrolling strip with Pause/Play, a still list under reduced motion, in both themes, with axe.
// Usage: node e2e/console-broadcast.mjs [out-dir]
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-console-broadcast";
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
const markup = "<b>Maintenance at six</b> tonight";

async function login(base, username, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 }, ...options });
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
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] },
      })
    ).violations.map((item) => item.id),
  );
  check(violations.length === 0, `${label} accessibility ${width}: ${violations}`);
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}`,
  );
  await page.setViewportSize({ width: 1400, height: 1100 });
}

async function addMessage(page, text, level) {
  await page.getByRole("button", { name: "Add broadcast message" }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^Message/).fill(text);
  await dialog.getByLabel("Level", { exact: true }).selectOption(level);
  await dialog.getByRole("button", { name: "Add message", exact: true }).click();
  await dialog.waitFor({ state: "hidden" });
}

async function checkTheme(base, theme) {
  const label = `${base || "root"} ${theme}`;
  const admin = await login(base, "admin", { colorScheme: theme });
  const member = await login(base, "bharat", { colorScheme: theme });
  const page = admin.page;
  const endpoint = origin + base + "/api/v1";

  await page.goto(origin + base + "/admin/broadcast");
  await page.getByRole("heading", { name: "Broadcast", exact: true }).waitFor();
  await page.getByText("No broadcast messages").waitFor();
  check(true, label + " empty list is explained");
  await audit(page, 1400, label + " empty");

  await addMessage(page, markup, "warning");
  await addMessage(page, "Library closed on Monday", "info");
  await page.getByText("Showing now").first().waitFor();
  check((await page.locator("tbody tr").count()) === 2, label + " both messages are listed");
  check((await page.locator("tbody b").count()) === 0, label + " admin table shows markup as typed");
  await audit(page, 1400, label + " table");
  await audit(page, 390, label + " table");
  await page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-${theme}-admin.png`, fullPage: true });

  await member.page.goto(origin + base + "/");
  const strip = member.page.getByTestId("broadcast-strip");
  await strip.waitFor();
  check((await strip.locator("b").count()) === 0, label + " strip shows markup as typed");
  const status = strip.getByRole("status");
  check((await status.getAttribute("aria-live")) === "polite", label + " status region is polite");
  check((await status.innerText()).includes(markup), label + " status region carries the text once");
  const track = strip.locator(".broadcast-strip__track");
  const state = () => track.evaluate((node) => getComputedStyle(node).animationPlayState);
  await member.page.mouse.move(700, 700);
  check((await state()) === "running", label + " strip scrolls");
  await strip.hover();
  check((await state()) === "paused", label + " strip pauses on hover");
  await member.page.mouse.move(700, 700);
  await strip.getByRole("button", { name: "Pause announcements" }).click();
  await member.page.mouse.move(700, 700);
  await strip.getByRole("button", { name: "Play announcements" }).waitFor();
  check((await state()) === "paused", label + " Pause button stops the motion");
  await strip.getByRole("button", { name: "Play announcements" }).click();
  await strip.getByRole("button", { name: "Pause announcements" }).focus();
  check((await state()) === "paused", label + " keyboard focus pauses the motion");
  await audit(member.page, 1400, label + " member with strip");
  await audit(member.page, 390, label + " member with strip");
  await member.page.screenshot({ path: `${output}/${base ? "prefix" : "root"}-${theme}-strip.png` });

  const reduced = await login(base, "chitra", { colorScheme: theme, reducedMotion: "reduce" });
  await reduced.page.goto(origin + base + "/");
  const still = reduced.page.getByTestId("broadcast-strip");
  await still.waitFor();
  check(
    (await still.getByRole("button").count()) === 0,
    label + " reduced motion has no moving strip control",
  );
  check(
    (await still.locator(".broadcast-strip__track").evaluate((n) => getComputedStyle(n).animationName)) ===
      "none",
    label + " reduced motion does not animate",
  );
  await audit(reduced.page, 1400, label + " reduced motion");
  await reduced.context.close();

  await page.getByRole("button", { name: "Turn off" }).first().click();
  await page.getByText("Turned off").waitFor();
  await member.page.reload();
  await member.page.getByTestId("broadcast-strip").getByText("Library closed on Monday").first().waitFor();
  check(
    (await member.page.getByTestId("broadcast-strip").getByRole("status").innerText()).includes(
      "Maintenance",
    ) === false,
    label + " a turned-off message disappears for everyone",
  );
  await page.getByRole("button", { name: "Turn on" }).click();
  await page.getByText("Turned off").waitFor({ state: "hidden" });

  await page.getByRole("button", { name: "Edit" }).nth(1).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^Message/).fill("Library closed on Tuesday");
  await dialog.getByRole("button", { name: "Save message" }).click();
  await dialog.waitFor({ state: "hidden" });
  await page.getByText("Library closed on Tuesday").waitFor();
  await page.getByRole("button", { name: /Move message 2 up/ }).click();
  await page.waitForFunction(() => document.querySelector("tbody tr")?.textContent?.includes("Tuesday"));
  check(true, label + " order can be changed");

  check(
    (await member.context.request.get(endpoint + "/admin/broadcasts")).status() === 403,
    label + " member denied",
  );
  const anonymous = await browser.newContext();
  check(
    (await anonymous.request.get(endpoint + "/site/broadcasts")).status() === 401,
    label + " signed-out 401",
  );
  await anonymous.close();

  for (const _ of [1, 2]) {
    await page.getByRole("button", { name: "Delete", exact: true }).first().click();
    const confirm = page.getByRole("dialog");
    check((await confirm.innerText()).includes("cannot be brought back"), label + " delete is confirmed");
    await confirm.getByRole("button", { name: "Delete broadcast message" }).click();
    await confirm.waitFor({ state: "hidden" });
  }
  await page.getByText("No broadcast messages").waitFor();
  await member.page.reload();
  await member.page.getByRole("button", { name: /^Account menu for / }).waitFor();
  check(
    (await member.page.getByTestId("broadcast-strip").count()) === 0,
    label + " deleted messages are gone",
  );
  await admin.context.close();
  await member.context.close();
}

for (const base of ["", "/labadda-staging"]) {
  for (const theme of ["light", "dark"]) await checkTheme(base, theme);
}
await browser.close();
console.log(`console-broadcast: ${checks} checks passed`);
