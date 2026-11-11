import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const browser = await chromium.launch({
    executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
  }),
  origin = "http://127.0.0.1:8080";
let checks = 0;
const check = (v, label) => {
  assert.ok(v, label);
  checks++;
  console.log("PASS " + label);
};
async function login(base, name) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }),
    page = await ctx.newPage(),
    errors = [];
  await ctx.addInitScript(() => {
    const Native = window.WebSocket;
    window.__sockets = [];
    window.WebSocket = class extends Native {
      constructor(...args) {
        super(...args);
        window.__sockets.push(this);
      }
    };
  });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill("fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return {
    ctx,
    page,
    errors,
    session,
    api: origin + base + "/api/v1",
    headers: { "X-CSRF-Token": session.csrf_token },
  };
}
async function call(a, path, body, method = body ? "POST" : "GET") {
  const r = await a.ctx.request.fetch(a.api + path, { method, headers: a.headers, data: body });
  assert.ok(r.ok(), await r.text());
  return r.json();
}
async function thread(a, base, ws, body) {
  await a.page.goto(origin + base + `/w/${ws}/chat`);
  await a.page
    .getByRole("listitem")
    .filter({ has: a.page.getByText(body, { exact: true }) })
    .getByRole("button", { name: "Open thread", exact: true })
    .click();
  return a.page.getByRole("region", { name: "Chat thread", exact: true });
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const ben = await login(base, "ben"),
      asha = await login(base, "asha"),
      admin = await login(base, "admin");
    const ws = (await call(ben, "/workspaces")).workspaces.find((w) => w.name === "Thin Films Section").id;
    const root = await call(asha, `/workspaces/${ws}/chat`, {
      body: "Research control plan",
      client_id: crypto.randomUUID(),
    });
    const region = await thread(ben, base, ws, root.body),
      other = await thread(asha, base, ws, root.body);
    await region.getByLabel("Thread reply", { exact: true }).fill("Unsent uncertainty question");
    await other.getByLabel("Thread reply", { exact: true }).fill("Add a witness coupon");
    await other.getByRole("button", { name: "Send reply", exact: true }).click();
    await other.getByText("Add a witness coupon", { exact: true }).waitFor();
    await region.getByRole("button", { name: "Refresh thread", exact: true }).click();
    await region.getByText("Add a witness coupon", { exact: true }).waitFor();
    check(
      (await region.getByLabel("Thread reply", { exact: true }).inputValue()) ===
        "Unsent uncertainty question",
      base + " thread refresh preserves reply draft",
    );
    await ben.page.route(
      "**/api/v1/workspaces/*/chat",
      async (route) => {
        if (route.request().method() !== "POST") return route.continue();
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await region.getByRole("button", { name: "Send reply", exact: true }).click();
    await region.getByRole("button", { name: "Retry same message", exact: true }).waitFor();
    check(
      await region.getByLabel("Thread reply", { exact: true }).isDisabled(),
      base + " unknown reply freezes original intent",
    );
    await region.getByRole("button", { name: "Retry same message", exact: true }).click();
    await region.getByText("Unsent uncertainty question", { exact: true }).waitFor();
    check(
      (await call(ben, `/workspaces/${ws}/chat/${root.id}/replies`)).messages.length === 2,
      base + " lost reply recovers one committed message",
    );
    for (const width of [1400, 390]) {
      await ben.page.setViewportSize({ width, height: 1100 });
      await ben.page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
      const violations = await ben.page.evaluate(async () =>
        (
          await window.axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
          })
        ).violations.map((v) => v.id),
      );
      check(!violations.length, base + " threads accessibility " + width + " " + violations);
      check(
        await ben.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        base + " threads overflow " + width,
      );
    }
    for (let i = 0; i < 52; i++)
      await call(asha, `/workspaces/${ws}/chat`, {
        body: "History sample " + i,
        client_id: crypto.randomUUID(),
      });
    await ben.page.getByRole("button", { name: "Refresh chat", exact: true }).click();
    await ben.page.getByText("History sample 51", { exact: true }).waitFor();
    let oldRelease, oldCaptured;
    const oldHold = new Promise((r) => (oldRelease = r)),
      oldReady = new Promise((r) => (oldCaptured = r));
    await ben.page.route(
      "**/api/v1/workspaces/*/chat?before=*",
      async (route) => {
        const response = await route.fetch();
        oldCaptured();
        await oldHold;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    const oldDelivered = ben.page.waitForResponse((r) => r.url().includes("/chat?before="));
    await ben.page.getByRole("button", { name: "Load earlier messages", exact: true }).click();
    await oldReady;
    await ben.page.getByRole("button", { name: "Return to latest messages", exact: true }).click();
    await ben.page.getByText("History sample 51", { exact: true }).waitFor();
    oldRelease();
    await (await oldDelivered).finished();
    await ben.page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    check(
      (await ben.page.getByText("History sample 51", { exact: true }).isVisible()) &&
        (await ben.page.getByRole("button", { name: "Return to latest messages", exact: true }).count()) ===
          0,
      base + " delayed older page cannot override latest view",
    );
    await ben.page.getByRole("button", { name: "Load earlier messages", exact: true }).click();
    await ben.page.getByRole("button", { name: "Return to latest messages", exact: true }).waitFor();
    const background = ben.page.waitForResponse(
      async (r) =>
        r.url().includes("/chat?after=") &&
        (await r.json()).messages.some((m) => m.body === "Newest history decision"),
    );
    await call(asha, `/workspaces/${ws}/chat`, {
      body: "Newest history decision",
      client_id: crypto.randomUUID(),
    });
    await (await background).finished();
    check(
      (await ben.page.getByRole("button", { name: "Return to latest messages", exact: true }).isVisible()) &&
        (await ben.page.getByRole("button", { name: "Load more new messages", exact: true }).isVisible()),
      base + " live updates retain earlier view and new-message notice",
    );
    await ben.page.getByRole("button", { name: "Return to latest messages", exact: true }).click();
    await ben.page.getByText("Newest history decision", { exact: true }).waitFor();
    check(true, base + " explicit return restores latest messages");
    // Hold a pre-disconnect HTTP snapshot; reconnect must queue another catch-up.
    let release, captured;
    const hold = new Promise((r) => (release = r)),
      ready = new Promise((r) => (captured = r));
    await ben.page.route(
      "**/api/v1/workspaces/*/chat?*",
      async (route) => {
        const response = await route.fetch();
        captured();
        await hold;
        await route.fulfill({ response });
      },
      { times: 1 },
    );
    await ben.page.getByRole("button", { name: "Refresh chat", exact: true }).click();
    await ready;
    const reconnected = ben.page.waitForEvent("websocket");
    await ben.page.evaluate(() => window.__sockets.at(-1).close());
    await call(asha, `/workspaces/${ws}/chat`, {
      body: "Offline control decision",
      client_id: crypto.randomUUID(),
    });
    await reconnected;
    release();
    await ben.page.getByText("Offline control decision", { exact: true }).waitFor();
    check(true, base + " reconnect queued behind held snapshot catches offline writes");
    await call(admin, `/admin/workspaces/${ws}/memberships/${ben.session.user.id}`, undefined, "DELETE");
    await ben.page.getByText("This chat is no longer available.", { exact: true }).waitFor();
    check(
      (await ben.page.getByLabel("Thread reply", { exact: true }).count()) === 0 &&
        (await ben.page.getByText("Research control plan", { exact: true }).count()) === 0,
      base + " revocation clears thread stream and composer",
    );
    check(!ben.errors.length && !asha.errors.length, base + " no browser exceptions");
    await Promise.all([ben.ctx.close(), asha.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${checks} chat thread browser checks passed`);
} finally {
  await browser.close();
}
