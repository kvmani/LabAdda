import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const require = createRequire(import.meta.url),
  { chromium } = require("playwright");
const origin = "http://127.0.0.1:8080",
  out = process.argv[2] ?? "/tmp/c4-collaboration";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
const shots = [];
const check = (v, label) => {
  assert.ok(v, label);
  checks++;
  console.log("PASS " + label);
};
async function login(base, name) {
  const ctx = await browser.newContext({
      viewport: { width: 1400, height: 1100 },
      timezoneId: "Asia/Kolkata",
    }),
    page = await ctx.newPage(),
    errors = [];
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
async function shot(a, file, label) {
  await a.page.screenshot({ path: out + "/" + file, fullPage: true });
  shots.push({ file, label });
}
const pdf = Buffer.from("%PDF-1.4\nSynthetic instrument handoff\n%%EOF");
try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    const created = await call(admin, "/admin/users", { username: "mira", display_name: "Mira Sen" });
    const fresh = await browser.newContext();
    assert.equal(
      (
        await fresh.request.post(admin.api + "/auth/activate", {
          data: { token: created.activation_token, password: "fixture-pass-123" },
        })
      ).status(),
      200,
    );
    await fresh.close();
    const people = {};
    for (const name of ["asha", "ben", "chen", "mira", "dana"]) people[name] = await login(base, name);
    const { ben, chen } = people,
      spaces = (await call(ben, "/workspaces")).workspaces,
      section = spaces.find((w) => w.name === "Thin Films Section"),
      division = spaces.find((w) => w.name === "Surface Science Division");
    const catalysis = (await call(chen, "/workspaces")).workspaces.find(
      (w) => w.name === "Catalysis Section",
    );
    await call(
      admin,
      `/admin/workspaces/${catalysis.id}/memberships`,
      { user_id: created.user.id, role: "member" },
      "PUT",
    );
    await ben.page.goto(origin + base + "/groups/new?conversation=1");
    await ben.page.getByLabel("Group name", { exact: true }).fill("Ben and Chen private handoff");
    await ben.page.getByLabel("Find colleagues", { exact: true }).fill("chen");
    await ben.page.getByRole("button", { name: /\+ Chen Li/ }).click();
    await ben.page.getByRole("button", { name: "Create group with 1 colleague", exact: true }).click();
    await ben.page.getByRole("heading", { level: 1, name: /Ben and Chen private handoff/ }).waitFor();
    const privateId = ben.page.url().match(/\/w\/([^/]+)/)[1],
      form = ben.page.getByRole("form", { name: "Send chat message", exact: true });
    check(ben.page.url().endsWith("/chat"), base + " private conversation opens a two-person group chat");
    await ben.page.route(
      "**/api/v1/uploads",
      async (route) => {
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await form
      .getByLabel("Attach files", { exact: true })
      .setInputFiles({ name: "instrument-handoff.pdf", mimeType: "application/pdf", buffer: pdf });
    await form.getByRole("button", { name: "Check upload result", exact: true }).waitFor();
    await form.getByRole("button", { name: "Check upload result", exact: true }).click();
    await form.getByRole("button", { name: "Remove file: instrument-handoff.pdf", exact: true }).waitFor();
    check(true, base + " lost upload reply recovers original file through receipt");
    await form
      .getByLabel("Message Ben and Chen private handoff", { exact: true })
      .fill("Private instrument handoff — check reference drift first.");
    await ben.page.route(
      "**/api/v1/workspaces/*/chat",
      async (route) => {
        if (route.request().method() !== "POST") return route.continue();
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await form.getByRole("button", { name: "Send", exact: true }).click();
    await form.getByRole("button", { name: "Retry same message", exact: true }).waitFor();
    check(
      await form.getByLabel("Attach files", { exact: true }).isDisabled(),
      base + " unknown message freezes file selection and destination",
    );
    await form.getByRole("button", { name: "Retry same message", exact: true }).click();
    await form.getByLabel("Message Ben and Chen private handoff", { exact: true }).waitFor();
    const messages = (await call(ben, `/workspaces/${privateId}/chat`)).messages;
    check(
      messages.length === 1 && messages[0].attachments.length === 1,
      base + " lost send reply recovers one message and one binding",
    );
    const file = messages[0].attachments[0];
    await chen.page.goto(origin + base + `/w/${privateId}/chat`);
    await chen.page.getByRole("link", { name: "instrument-handoff.pdf", exact: true }).waitFor();
    check(
      Buffer.from(await (await chen.ctx.request.get(origin + file.url)).body()).equals(pdf),
      base + " colleague downloads authorized private handoff",
    );
    for (const actor of [people.asha, people.mira, people.dana, admin])
      check(
        (await actor.ctx.request.get(origin + file.url)).status() === 404,
        base + " sibling division colleague/admin cannot retrieve private file",
      );
    await shot(
      chen,
      (base ? "prefix" : "root") + "-private-chat.png",
      "Private Ben/Chen handoff with an actual validated PDF attachment",
    );
    await ben.page
      .getByRole("listitem")
      .filter({ has: ben.page.getByText(messages[0].body, { exact: true }) })
      .getByRole("button", { name: "Open thread", exact: true })
      .click();
    const thread = ben.page.getByRole("region", { name: "Chat thread", exact: true });
    await thread
      .getByLabel("Attach files", { exact: true })
      .setInputFiles({ name: "replicate-plan.pdf", mimeType: "application/pdf", buffer: pdf });
    await thread.getByRole("button", { name: "Remove file: replicate-plan.pdf", exact: true }).waitFor();
    await thread.getByLabel("Thread reply", { exact: true }).fill("Three replicates and a blank.");
    await thread.getByRole("button", { name: "Send reply", exact: true }).click();
    await thread.getByRole("link", { name: "replicate-plan.pdf", exact: true }).waitFor();
    check(true, base + " reply shares a validated file inside original thread audience");
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
      check(!violations.length, base + " attachments accessibility " + width + " " + violations);
      check(
        await ben.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        base + " attachments overflow " + width,
      );
    }
    await ben.page.setViewportSize({ width: 1400, height: 1100 });
    const common = await call(ben, "/groups", {
      name: "Aurora C4 research discussion",
      description: "Synthetic collaboration across Thin Films, Catalysis and Surface Science Division.",
      member_ids: Object.values(people).map((a) => a.session.user.id),
    });
    const ideas = [
      "Asha: retain a witness coupon.",
      "Ben: sample IDs mapped to run IDs.",
      "Chen: include GC blanks and three replicates.",
      "Mira: cap transfer before XPS.",
      "Dana: review uncertainty at the division gate.",
    ];
    for (const [i, a] of Object.values(people).entries()) {
      await call(a, `/workspaces/${common.id}/chat`, { body: ideas[i], client_id: crypto.randomUUID() });
      await call(a, `/workspaces/${common.id}/board/ops`, {
        epoch: 1,
        type: "add",
        op_id: crypto.randomUUID(),
        object_id: crypto.randomUUID(),
        payload: {
          kind: "sticky",
          data: {
            x: 30 + i * 190,
            y: 90,
            text: ideas[i],
            color: ["#fff59d", "#b3e5fc", "#ffccbc", "#c8e6c9", "#fff59d"][i],
          },
        },
      });
    }
    for (const a of Object.values(people)) {
      await a.page.goto(origin + base + `/w/${common.id}/board`);
      await a.page.getByRole("button", { name: "Fit", exact: true }).click();
    }
    await ben.page.getByText(/5 here:/).waitFor();
    check(true, base + " five real sessions collaborate across sibling sections and parent division");
    await shot(
      ben,
      (base ? "prefix" : "root") + "-five-person-board.png",
      "Five-person cross-section research plan with shared native stickies",
    );
    await people.dana.page.goto(origin + base + `/w/${common.id}/chat`);
    await people.dana.page.getByText(ideas[4], { exact: true }).waitFor();
    await shot(
      people.dana,
      (base ? "prefix" : "root") + "-group-chat.png",
      "Five researchers discuss controls and division review",
    );
    await ben.page.goto(origin + base + "/groups/new?conversation=1");
    await ben.page.getByLabel("Group name", { exact: true }).fill("Uncertain conversation review");
    await ben.page.getByLabel("Find colleagues", { exact: true }).fill("asha");
    await ben.page.getByRole("button", { name: /\+ Asha Rao/ }).click();
    await ben.page.route(
      "**/api/v1/groups",
      async (route) => {
        await route.fetch();
        await route.abort();
      },
      { times: 1 },
    );
    await ben.page.getByRole("button", { name: "Create group with 1 colleague", exact: true }).click();
    await ben.page.getByText("Creation may have succeeded.", { exact: false }).waitFor();
    check(
      await ben.page.getByRole("button", { name: "Create group with 1 colleague", exact: true }).isDisabled(),
      base + " uncertain private-group creation blocks blind duplicate submit",
    );
    await ben.page.getByRole("link", { name: "Uncertain conversation review", exact: false }).waitFor();
    check(true, base + " group list reveals committed result for manual recovery");
    await chen.page.goto(origin + base + `/w/${privateId}/chat`);
    await chen.page.getByRole("link", { name: "instrument-handoff.pdf", exact: true }).waitFor();
    await call(ben, `/groups/${privateId}/members/${chen.session.user.id}`, undefined, "DELETE");
    await chen.page
      .getByText(/This chat is no longer available\.|Workspace not available/)
      .first()
      .waitFor();
    check(
      (await chen.ctx.request.get(origin + file.url)).status() === 404,
      base + " removed colleague loses attachment and chat access",
    );
    check(
      Object.values(people).every((a) => !a.errors.length),
      base + " no browser exceptions",
    );
    await Promise.all([...Object.values(people).map((a) => a.ctx.close()), admin.ctx.close()]);
  }
  writeFileSync(out + "/report.json", JSON.stringify({ checks, shots }, null, 2));
  writeFileSync(
    out + "/index.html",
    '<!doctype html><meta charset="utf-8"><title>C4 synthetic collaboration</title><style>body{font:16px system-ui;max-width:1400px;margin:24px auto}img{max-width:100%}</style><h1>C4 synthetic collaboration</h1>' +
      shots.map((s) => `<h2>${s.label}</h2><img src="${s.file}" alt="${s.label}">`).join(""),
  );
  console.log(`${checks} chat attachment browser checks passed`);
} finally {
  await browser.close();
}
