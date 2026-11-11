// P8 My profile: record, access, password change and sessions at the root and prefixed instance.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-profile";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
const OLD = "fixture-pass-123";
const NEW = "a-brand-new-passphrase";
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
async function login(base, username, password = OLD) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
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
  check(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    `${label} fits ${width}`,
  );
}
async function fillPasswords(page, current, next, again = next) {
  await page.getByLabel(/^Current password/).fill(current);
  await page.getByLabel(/^New password/).fill(next);
  await page.getByLabel(/^Repeat new password/).fill(again);
}
async function run(base, name) {
  const label = base || "root";
  const first = await login(base, name);
  const second = await login(base, name);
  const page = first.page;
  await page.getByRole("button", { name: /^Account menu for / }).click();
  const items = await page.getByRole("menuitem").allInnerTexts();
  check(items[0] === "My profile", `${label} My profile is the first account menu item`);
  await page.getByRole("menuitem", { name: "My profile" }).click();
  await page.getByRole("heading", { name: "My profile", level: 1 }).waitFor();
  check(new URL(page.url()).pathname === base + "/profile", `${label} opens at /profile`);
  await page.getByText("Employee number", { exact: true }).waitFor();
  check(
    (await page.getByRole("heading", { name: "My access" }).count()) === 1,
    `${label} shows record and access`,
  );
  check(
    (await page.getByRole("textbox").count()) === 0 || (await page.locator("dl input").count()) === 0,
    `${label} record is read-only`,
  );
  await page.getByText("This session", { exact: true }).waitFor();
  const ends = page.getByRole("button", { name: "Sign out this session (Chrome on Linux)" });
  await ends.first().waitFor();
  check((await ends.count()) >= 1, `${label} lists the other session with a sign-out button`);
  await audit(page, 1400, label + " profile");
  await audit(page, 390, label + " profile");
  await page.screenshot({ path: `${output}/${label.replace("/", "")}-profile-390.png`, fullPage: true });
  await page.setViewportSize({ width: 1400, height: 1100 });

  // Wrong current password keeps the draft and names the field.
  await fillPasswords(page, "not-my-password", NEW);
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByText("Your current password is not correct.").waitFor();
  check(
    (await page.getByLabel(/^New password/).inputValue()) === NEW,
    `${label} failed password change keeps the draft`,
  );
  // Weak password.
  await fillPasswords(page, OLD, "short");
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByText("Use at least 10 characters.", { exact: true }).last().waitFor();
  check(true, `${label} weak password is explained`);
  await fillPasswords(page, OLD, NEW, "different-passphrase");
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByText("The two new passwords do not match.").waitFor();
  check(true, `${label} mismatched repeat is explained`);

  // Success ends the other browser immediately and keeps this one.
  await fillPasswords(page, OLD, NEW);
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByText(/Your password was changed\. 1 other session was signed out\./).waitFor();
  check(true, `${label} password change reports signed-out sessions`);
  await page.reload();
  await page.getByRole("heading", { name: "My profile", level: 1 }).waitFor();
  check(true, `${label} current browser stays signed in`);
  await second.page.reload();
  await second.page.getByLabel("Username", { exact: true }).waitFor();
  check(true, `${label} other browser is signed out`);

  // Sign out one session by hand with the new password.
  const third = await login(base, name, NEW);
  await page.reload();
  await page.getByRole("button", { name: "Sign out this session (Chrome on Linux)" }).first().click();
  await page.getByText("Signed out Chrome on Linux.").waitFor();
  await third.page.reload();
  await third.page.getByLabel("Username", { exact: true }).waitFor();
  check(true, `${label} signing out a session ends it`);

  // Restore the fixture password so later suites are unaffected.
  await fillPasswords(page, NEW, OLD);
  await page.getByRole("button", { name: "Change password", exact: true }).click();
  await page.getByText(/Your password was changed\./).waitFor();
  await page.screenshot({ path: `${output}/${label.replace("/", "")}-profile-1400.png`, fullPage: true });
  for (const part of [first, second, third]) await part.context.close();
}
try {
  await run("", "eli");
  await run("/labadda-staging", "eli");
  console.log(`profile: ${checks} checks passed`);
} finally {
  await browser.close();
}
