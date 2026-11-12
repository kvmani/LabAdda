// Shared helpers for the browser checks: browser launch, sign-in, API calls, counted checks,
// accessibility scan and WebSocket observation. Suites import this instead of copying it.
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

export const origin = "http://127.0.0.1:8080";
export const fixturePassword = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
export const bases = ["", "/labadda-staging"];

const axeSource = require.resolve("../../frontend/node_modules/axe-core/axe.min.js");
const wcagTags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** Starts a browser and returns the helpers one suite needs; call `close()` in a finally block. */
export async function startHarness({ timezoneId } = {}) {
  const browser = await chromium.launch({
    executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
  });
  let checkCount = 0;

  function check(value, label) {
    assert.ok(value, label);
    checkCount += 1;
    console.log("PASS " + label);
  }

  async function login(base, name, { trackSockets = false, password = fixturePassword } = {}) {
    const contextOptions = { viewport: { width: 1400, height: 1100 } };
    if (timezoneId) contextOptions.timezoneId = timezoneId;
    const ctx = await browser.newContext(contextOptions);
    const page = await ctx.newPage();
    const errors = [];
    const sockets = trackSockets ? observeSockets(ctx, page) : undefined;
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(origin + base + "/");
    await page.getByLabel("Username").fill(name);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: /^Account menu for / }).waitFor();
    const sessionResponse = await ctx.request.get(origin + base + "/api/v1/auth/session");
    const session = await sessionResponse.json();
    return {
      ctx,
      page,
      errors,
      session,
      sockets,
      api: origin + base + "/api/v1",
      headers: { "X-CSRF-Token": session.csrf_token },
    };
  }

  /** Axe scan and side-scroll check at desktop and phone width, labelled "<base> <label> ...". */
  async function checkLayouts(user, base, label) {
    for (const width of [1400, 390]) {
      await user.page.setViewportSize({ width, height: 1100 });
      const violations = await axeViolations(user.page);
      check(
        violations.length === 0,
        base + " " + label + " accessibility " + width + " " + violations.join(","),
      );
      check(await hasNoSideScroll(user.page), base + " " + label + " no overflow " + width);
    }
    await user.page.setViewportSize({ width: 1400, height: 1100 });
  }

  return {
    browser,
    check,
    checkLayouts,
    login,
    checks: () => checkCount,
    close: () => browser.close(),
  };
}

/** Calls the API as a signed-in user and returns the parsed body; fails on a non-2xx status. */
export async function call(user, path, body, method = body ? "POST" : "GET") {
  const response = await user.ctx.request.fetch(user.api + path, {
    method,
    headers: user.headers,
    data: body,
  });
  assert.ok(response.ok(), await response.text());
  return response.json();
}

/** Ids of the WCAG A/AA rules the current page breaks. */
export async function axeViolations(page) {
  await page.addScriptTag({ path: axeSource });
  return page.evaluate(async (tags) => {
    const result = await window.axe.run(document, { runOnly: { type: "tag", values: tags } });
    return result.violations.map((violation) => violation.id);
  }, wcagTags);
}

export function hasNoSideScroll(page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
}

/**
 * Records every socket the page opens and every frame it receives, so a suite can wait for
 * the server to confirm a subscription before it acts. `frames` holds parsed JSON frames.
 */
function observeSockets(ctx, page) {
  const state = { frames: [], listeners: new Set(), inFlight: 0 };
  trackApiRequests(page, state);
  ctx.addInitScript(() => {
    const NativeSocket = window.WebSocket;
    window.__sockets = [];
    window.WebSocket = class extends NativeSocket {
      constructor(...args) {
        super(...args);
        window.__sockets.push(this);
      }
    };
  });
  page.on("websocket", (socket) =>
    socket.on("framereceived", (frame) => {
      let parsed;
      try {
        parsed = JSON.parse(String(frame.payload));
      } catch {
        return;
      }
      state.frames.push(parsed);
      state.listeners.forEach((listener) => listener());
    }),
  );
  return state;
}

function trackApiRequests(page, state) {
  const isApi = (request) => request.url().includes("/api/v1/");
  page.on("request", (request) => {
    if (isApi(request)) state.inFlight += 1;
  });
  const finished = (request) => {
    if (isApi(request)) state.inFlight -= 1;
  };
  page.on("requestfinished", finished);
  page.on("requestfailed", finished);
}

/**
 * Waits until the tab has no API request in flight across two painted frames, so a follow-up
 * request chained to a response (such as an unread-count reload) cannot overlap what the suite does next.
 */
export async function settleRequests(user) {
  for (let attempt = 0; attempt < 500; attempt++) {
    await nextPaint(user.page);
    if (user.sockets.inFlight !== 0) continue;
    await nextPaint(user.page);
    if (user.sockets.inFlight === 0) return;
  }
  throw new Error("API requests did not settle");
}

/** Number of frames received so far; pass it as `since` to ignore earlier frames. */
export function frameMark(user) {
  return user.sockets.frames.length;
}

/** Resolves when a frame received after `since` matches; rejects after the Playwright timeout. */
export function waitForFrame(user, matches, since = 0) {
  const state = user.sockets;
  return new Promise((resolve, reject) => {
    const find = () => state.frames.slice(since).find(matches);
    const timer = setTimeout(() => {
      state.listeners.delete(listener);
      reject(new Error("timed out waiting for a socket frame"));
    }, 30000);
    function listener() {
      const frame = find();
      if (!frame) return;
      clearTimeout(timer);
      state.listeners.delete(listener);
      resolve(frame);
    }
    state.listeners.add(listener);
    listener();
  });
}

/** Waits until the server has confirmed this tab's subscription to a workspace. */
export function waitForSubscribed(user, workspaceId, since = 0) {
  return waitForFrame(
    user,
    (frame) => frame.type === "subscribed" && frame.workspace_id === workspaceId,
    since,
  );
}

/**
 * Holds the first request matching `pattern` after the server has answered it.
 * `captured` resolves once the answer is in hand; `release()` lets the page receive it;
 * `request()` is the held request, once captured.
 */
export async function holdFirstResponse(page, pattern) {
  let release;
  let markCaptured;
  let heldRequest;
  const hold = new Promise((resolve) => (release = resolve));
  const captured = new Promise((resolve) => (markCaptured = resolve));
  await page.route(
    pattern,
    async (route) => {
      heldRequest = route.request();
      const response = await route.fetch();
      markCaptured();
      await hold;
      await route.fulfill({ response });
    },
    { times: 1 },
  );
  return { captured, release, request: () => heldRequest };
}

/** Waits two animation frames so a rendered response has reached the screen. */
export function nextPaint(page) {
  return page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
}

/** Aborts the browser's view of the next matching request after the server has answered it. */
export async function loseNextResponse(page, pattern, { onlyPost = false, onlyPut = false } = {}) {
  await page.route(
    pattern,
    async (route) => {
      const method = route.request().method();
      if (onlyPost && method !== "POST") return route.continue();
      if (onlyPut && method !== "PUT") return route.continue();
      await route.fetch();
      await route.abort();
    },
    { times: 1 },
  );
}
