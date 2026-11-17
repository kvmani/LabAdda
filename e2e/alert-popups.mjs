// Real-server pop-up checks and screenshots; supports root and prefixed instances.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8010";
const bases = process.argv.slice(2);
const shots = process.env.LABADDA_E2E_SHOTS ?? "/tmp/labadda-screenshots";
mkdirSync(shots, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
function check(value, label) {
  if (!value) throw new Error(label);
  console.log(`PASS ${label}`);
}
try {
  for (const base of bases.length ? bases : [""]) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    await page.goto(`${origin}${base}/login`);
    await page.getByLabel("Username").fill("asha");
    await page.getByLabel("Password").fill("fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: /^Account menu for/ }).waitFor();

    const session = await (await context.request.get(`${origin}${base}/api/v1/auth/session`)).json();
    const csrf = session.csrf_token;
    const api = async (path, data) => {
      const response = await context.request.post(`${origin}${base}/api/v1${path}`, {
        data,
        headers: { "X-CSRF-Token": csrf, Origin: origin },
      });
      check(response.ok(), `${path}: ${response.status()}`);
      return response.json();
    };
    await api("/notifications/read-all", {});
    const title = "Project Tejas weekly research review";
    await api("/calendar/events", {
      scope_kind: "personal",
      title,
      starts_at: new Date(Date.now() + 10 * 60000).toISOString(),
      ends_at: new Date(Date.now() + 40 * 60000).toISOString(),
      all_day: false,
    });
    // The scheduler delivers the real reminder; no route interception or fake DOM.
    await page.goto(`${origin}${base}/calendar`);
    await page.getByRole("button", { name: "Enable chime" }).click();
    await page.getByRole("button", { name: "Mute chime" }).waitFor();
    const alerts = page.getByRole("complementary", { name: "Live alerts", exact: true });
    await alerts.getByText(title, { exact: true }).waitFor({ timeout: 50000 });
    const tag = base ? "prefix" : "root";
    await page.screenshot({ path: `${shots}/${tag}-calendar-reminder.png`, fullPage: true });
    const card = alerts.locator("section").filter({ hasText: title });
    await card.getByRole("button", { name: "Dismiss", exact: true }).click();
    let notifications = await (await context.request.get(`${origin}${base}/api/v1/notifications`)).json();
    check(
      notifications.items.some((n) => n.title === title && !n.read),
      "Dismiss keeps reminder unread",
    );
    await page.reload();
    await alerts.getByText(title, { exact: true }).waitFor();
    await alerts
      .locator("section")
      .filter({ hasText: title })
      .getByRole("button", { name: "Mark as read", exact: true })
      .click();
    await alerts.getByText(title, { exact: true }).waitFor({ state: "hidden" });
    notifications = await (await context.request.get(`${origin}${base}/api/v1/notifications`)).json();
    check(
      notifications.items.some((n) => n.title === title && n.read),
      "Read acknowledgement persisted",
    );
    const sender = await browser.newContext();
    const login = await sender.request.post(`${origin}${base}/api/v1/auth/login`, {
      data: { username: "bharat", password: "fixture-pass-123" },
      headers: { Origin: origin },
    });
    const senderSession = await login.json();
    const workspace = session.user.home_workspace_id;
    const text = "The Thin Films meeting notes are ready. Please review before our discussion.";
    const sent = await sender.request.post(`${origin}${base}/api/v1/workspaces/${workspace}/chat`, {
      data: { body: text, client_id: `popup-${Date.now()}` },
      headers: { Origin: origin, "X-CSRF-Token": senderSession.csrf_token },
    });
    check(sent.ok(), "Colleague sends real chat message");
    await alerts.getByText(text, { exact: true }).waitFor();
    await page.screenshot({ path: `${shots}/${tag}-chat-popup.png`, fullPage: true });
    await alerts
      .locator("section")
      .filter({ hasText: text })
      .getByRole("button", { name: "Mark as read", exact: true })
      .click();
    await alerts.getByText(text, { exact: true }).waitFor({ state: "hidden" });
    const history = await (
      await context.request.get(`${origin}${base}/api/v1/workspaces/${workspace}/chat`)
    ).json();
    check(history.last_read_seq >= (await sent.json()).seq, "Chat read cursor saved");
    for (const [name, route] of [
      ["whiteboard", "/whiteboard"],
      ["team-whiteboard", `/w/${workspace}/board`],
      ["chat", `/w/${workspace}/chat`],
      ["noticeboard", `/w/${workspace}/noticeboard`],
      ["tasks", "/my-tasks"],
      ["notes", "/notes"],
    ]) {
      await page.goto(`${origin}${base}${route}`);
      await page.getByRole("button", { name: /^Account menu for/ }).waitFor();
      await page.waitForTimeout(1200);
      if (name === "whiteboard") {
        const canvas = page.getByLabel("Whiteboard drawing surface", { exact: true });
        await canvas.waitFor();
        const bounds = await canvas.boundingBox();
        await page.mouse.move(bounds.x + 120, bounds.y + 220);
        await page.mouse.down();
        await page.mouse.move(bounds.x + 260, bounds.y + 100, { steps: 18 });
        await page.mouse.move(bounds.x + 390, bounds.y + 160, { steps: 18 });
        await page.mouse.move(bounds.x + 510, bounds.y + 70, { steps: 18 });
        await page.mouse.up();
        await page.getByRole("button", { name: "💾 Save", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".save-state")?.textContent === "Saved");
      }
      await page.screenshot({ path: `${shots}/${tag}-${name}.png`, fullPage: true });
    }
    await sender.close();
    await context.close();
  }
} finally {
  await browser.close();
}
