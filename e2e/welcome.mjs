// H4 browser check: a new person sees the first-use welcome once, can dismiss it with the keyboard,
// never sees it again, and the what's-new page is reachable from Help. Fixture people start welcomed.
// Usage: node e2e/welcome.mjs [out-dir]
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080",
  out = process.argv[2] ?? "/tmp/welcome-check",
  axeSource = require.resolve("../frontend/node_modules/axe-core/axe.min.js"),
  password = "fixture-pass-123";
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

async function apiLogin(base, username, pass = password) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } }),
    api = origin + base + "/api/v1",
    response = await context.request.post(api + "/auth/login", { data: { username, password: pass } });
  assert.equal(response.status(), 200);
  const session = await response.json();
  return { context, api, headers: { "X-CSRF-Token": session.csrf_token }, session };
}

async function send(actor, method, path, data) {
  const response = await actor.context.request.fetch(actor.api + path, {
    method,
    headers: actor.headers,
    data,
  });
  assert.ok(response.ok(), `${method} ${path}: ${await response.text()}`);
  return response.json();
}

async function newcomer(base, admin, unit, tag) {
  const username = `welcome${tag}${Date.now() % 1000000}`,
    created = await send(admin, "POST", "/admin/users", { username, display_name: `Newcomer ${tag}` });
  await send(admin, "PUT", `/admin/workspaces/${unit}/memberships`, { user_id: created.user.id });
  const fresh = await browser.newContext();
  const activated = await fresh.request.post(admin.api + "/auth/activate", {
    data: { token: created.activation_token, password },
  });
  assert.equal(activated.status(), 200);
  await fresh.close();
  const person = await apiLogin(base, username);
  await send(person, "PUT", "/me/home", { workspace_id: unit });
  const page = await person.context.newPage();
  // The help home is narrow-screen clean, so the check measures the panel and not a wide workspace page.
  await page.goto(origin + base + "/help");
  return { ...person, page, username };
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

const welcome = (page) => page.getByRole("region", { name: /^Welcome to LabAdda/ });

try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await apiLogin(base, "admin"),
      units = (await send(admin, "GET", "/admin/workspaces")).workspaces,
      unit = units.find((w) => w.name === "Thin Films Section").id,
      where = base || "root";

    const keyboard = await newcomer(base, admin, unit, "k");
    await welcome(keyboard.page).waitFor();
    await keyboard.page.getByText(/^Your home unit is/).waitFor();
    const text = (await welcome(keyboard.page).innerText()).replace(/\s+/g, " ");
    check(text.includes("Your home unit is Thin Films Section"), `${where}: welcome names the home unit`);
    for (const word of ["Noticeboard", "Whiteboard", "Chat", "Help"])
      check(text.includes(word), `${where}: welcome mentions ${word}`);
    await keyboard.page.screenshot({ path: `${out}/welcome${base.replace("/", "-")}.png` });
    await audit(keyboard.page, 1400, `${where}: welcome`);
    await audit(keyboard.page, 390, `${where}: welcome`);
    await keyboard.page.setViewportSize({ width: 1400, height: 1000 });
    await keyboard.page.getByRole("button", { name: "Got it, hide this" }).focus();
    await keyboard.page.keyboard.press("Enter");
    await welcome(keyboard.page).waitFor({ state: "detached" });
    check(true, `${where}: Enter on the button hides the welcome`);
    await keyboard.page.reload();
    await keyboard.page.getByRole("button", { name: /^Account menu for / }).waitFor();
    check((await welcome(keyboard.page).count()) === 0, `${where}: the welcome does not return after reload`);
    const again = await send(keyboard, "GET", "/auth/session");
    check(!again.welcome_pending && !again.whats_new_pending, `${where}: the server remembers the dismissal`);

    const escape = await newcomer(base, admin, unit, "e");
    await welcome(escape.page).waitFor();
    await welcome(escape.page).getByRole("link", { name: "Help", exact: true }).focus();
    await escape.page.keyboard.press("Escape");
    await welcome(escape.page).waitFor({ state: "detached" });
    check(true, `${where}: Escape hides the welcome`);

    const staff = await admin.context.newPage();
    await staff.goto(origin + base + "/");
    await staff.getByRole("button", { name: /^Account menu for / }).waitFor();
    check((await welcome(staff).count()) === 0, `${where}: a welcomed person sees no panel`);

    await keyboard.page.goto(origin + base + "/help");
    await keyboard.page.getByRole("link", { name: "What is new in this release" }).click();
    await keyboard.page.getByRole("heading", { level: 1, name: "What is new" }).waitFor();
    check(true, `${where}: Help links to what is new`);
    await audit(keyboard.page, 1400, `${where}: what is new`);
    await audit(keyboard.page, 390, `${where}: what is new`);
    for (const actor of [keyboard, escape, admin]) await actor.context.close();
  }
  console.log(`welcome: ${checks} checks passed`);
} finally {
  await browser.close();
}
