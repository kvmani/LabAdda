// Real app simulation: fresh disposable fictional fixtures, five isolated browser contexts.
// NODE_PATH must expose Playwright; run against a dedicated dev/test instance only.
import { createRequire } from "node:module";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const origin = process.argv[2] ?? "http://127.0.0.1:8010";
const out = resolve(process.argv[3] ?? join(root, "var/research-day"));
if (
  process.argv[4] !== "--synthetic-instance" ||
  !["127.0.0.1", "localhost"].includes(new URL(origin).hostname)
)
  throw Error("Use an explicitly isolated local synthetic instance and --synthetic-instance");
const fixture = JSON.parse(readFileSync(join(root, "fixtures/research-day/scenario.json")));
const objects = JSON.parse(readFileSync(join(root, "fixtures/research-day/board-objects.json")));
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
mkdirSync(out, { recursive: true });
const checks = [],
  shots = [],
  contexts = [],
  errors = [];
function check(value, label) {
  assert.ok(value, label);
  checks.push(label);
  console.log(`PASS ${label}`);
}
async function api(actor, path, data, expected = 200) {
  const r =
    data === undefined
      ? await actor.ctx.request.get(origin + "/api/v1" + path)
      : await actor.ctx.request.post(origin + "/api/v1" + path, {
          data,
          headers: { "X-CSRF-Token": actor.csrf },
        });
  assert.equal(r.status(), expected, `${path}: ${await r.text()}`);
  return r.json();
}
async function actor(browser, username, ui = true) {
  const ctx = await browser.newContext({
    viewport: { width: 1500, height: 1120 },
    timezoneId: "Asia/Kolkata",
  });
  contexts.push(ctx);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (!r.url().startsWith(origin) && !r.url().startsWith("data:")) errors.push("External request");
  });
  if (ui) {
    await page.goto(origin);
    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  } else {
    const r = await ctx.request.post(origin + "/api/v1/auth/login", { data: { username, password } });
    assert.equal(r.status(), 200);
  }
  const session = await (await ctx.request.get(origin + "/api/v1/auth/session")).json();
  return { username, ctx, page, csrf: session.csrf_token, id: session.user.id };
}
function pdf(lines) {
  const stream =
    "BT /F1 12 Tf 48 760 Td " +
    lines.map((s, i) => `${i ? "0 -26 Td " : ""}(${s.replace(/[()\\]/g, "\\$&")}) Tj`).join("\n") +
    " ET";
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
  ];
  let text = "%PDF-1.4\n";
  const offsets = [0];
  for (const [i, obj] of objs.entries()) {
    offsets.push(Buffer.byteLength(text));
    text += `${i + 1} 0 obj\n${obj}\nendobj\n`;
  }
  const xref = Buffer.byteLength(text);
  text +=
    `xref\n0 6\n0000000000 65535 f \n` +
    offsets
      .slice(1)
      .map((o) => `${String(o).padStart(10, "0")} 00000 n \n`)
      .join("");
  return Buffer.from(text + `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
}
async function upload(a, name, mimeType, buffer, status = 201) {
  const r = await a.ctx.request.post(origin + "/api/v1/uploads", {
    headers: { "X-CSRF-Token": a.csrf },
    multipart: { file: { name, mimeType, buffer } },
  });
  assert.equal(r.status(), status, await r.text());
  return r.json();
}
async function view(a, workspace, tab) {
  await a.page.goto(`${origin}/w/${workspace}/${tab}`);
  await a.page.getByRole("heading", { level: 1 }).waitFor();
}
async function shot(a, file, caption) {
  await a.page.screenshot({ path: join(out, file), fullPage: true });
  shots.push({ file, caption, actor: a.username });
}
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
try {
  const admin = await actor(browser, "admin", false);
  const listed = await api(admin, "/admin/workspaces");
  const spaces = Object.fromEntries(listed.workspaces.map((w) => [w.name, w.id]));
  const users = (await api(admin, "/admin/users")).users;
  check(
    !listed.workspaces.some((w) => w.name === fixture.group),
    "dedicated instance has no previous research scenario",
  );
  let mira = users.find((u) => u.username === "mira");
  if (!mira) {
    const created = await api(admin, "/admin/users", { username: "mira", display_name: "Mira Sen" }, 201);
    const fresh = await browser.newContext();
    contexts.push(fresh);
    const activated = await fresh.request.post(origin + "/api/v1/auth/activate", {
      data: { token: created.activation_token, password },
    });
    assert.equal(activated.status(), 200);
    mira = created.user;
  }
  const member = await admin.ctx.request.put(
    origin + `/api/v1/admin/workspaces/${spaces["Catalysis Section"]}/memberships`,
    { headers: { "X-CSRF-Token": admin.csrf }, data: { user_id: mira.id } },
  );
  assert.equal(member.status(), 200);
  const people = {};
  for (const name of fixture.participants) people[name] = await actor(browser, name);
  check(Object.keys(people).length === 5, "five separate browser sessions signed in");
  const { ben, chen, dana, asha } = people;
  const group = await api(
    ben,
    "/groups",
    {
      name: fixture.group,
      description: "Joint Thin Films / Catalysis working group. Synthetic scenario.",
      member_ids: fixture.participants.filter((n) => n !== "ben").map((n) => people[n].id),
    },
    201,
  );
  const privateGroup = await api(
    ben,
    "/groups",
    {
      name: fixture.private_group,
      description: "Two-person preliminary instrument handoff.",
      member_ids: [chen.id],
    },
    201,
  );
  for (const a of Object.values(people)) await view(a, group.id, "board");
  for (let i = 0; i < objects.length; i += 12)
    await Promise.all(
      objects.slice(i, i + 12).map((o, j) =>
        api(people[o.actor], `/workspaces/${group.id}/board/ops`, {
          epoch: 1,
          type: "add",
          op_id: `research-op-${i + j}`,
          object_id: `research-object-${i + j}`,
          payload: { kind: o.kind, data: o.data },
        }),
      ),
    );
  const first = objects[0];
  const retry = await api(people[first.actor], `/workspaces/${group.id}/board/ops`, {
    epoch: 1,
    type: "add",
    op_id: "research-op-0",
    object_id: "research-object-0",
    payload: { kind: first.kind, data: first.data },
  });
  check(retry.duplicate === true, "retry keeps the same board operation instead of duplicating ink");
  const state = await api(ben, `/workspaces/${group.id}/board`);
  check(state.revision === objects.length, "all handwritten strokes and native stickies committed");
  check(
    new Set(state.ops.map((o) => o.actor_id)).size === 5,
    "board history attributes edits to all five researchers",
  );
  await ben.ctx.setOffline(true);
  await api(people.mira, `/workspaces/${group.id}/board/ops`, {
    epoch: 1,
    type: "add",
    op_id: "research-network-check",
    object_id: "network-check",
    payload: {
      kind: "stroke",
      data: {
        points: [
          [46, 550],
          [110, 554],
          [180, 550],
        ],
        color: "#c62828",
        width: 2,
      },
    },
  });
  await ben.ctx.setOffline(false);
  await ben.page.reload();
  const caughtUp = await api(ben, `/workspaces/${group.id}/board`);
  check(caughtUp.revision === state.revision + 1, "offline researcher catches up after reconnect");
  for (const [i, [name, body]] of fixture.chat.entries())
    await api(people[name], `/workspaces/${group.id}/chat`, { body, client_id: `research-chat-${i}` }, 201);
  for (const [name, section, body] of [
    [
      "asha",
      "Thin Films Section",
      "Preparation log / batch AUR-40: thickness 40 nm. Witness coupon retained. Raw deposition settings stay in this section.",
    ],
    [
      "chen",
      "Catalysis Section",
      "GC queue / batch AUR-40: reference, blank, then three replicates. Preliminary chromatograms stay in Catalysis.",
    ],
  ])
    await api(
      people[name],
      `/workspaces/${spaces[section]}/posts`,
      { body, client_id: `research-section-${name}` },
      201,
    );
  await api(
    dana,
    `/workspaces/${spaces["Surface Science Division"]}/posts`,
    { body: fixture.division_notice, kind: "official", client_id: "research-division-review" },
    201,
  );
  await api(
    ben,
    "/notes",
    {
      title: "Private: check reference drift",
      body: "Repeat the 40 nm reference before sharing a conclusion. This note must remain mine.",
    },
    201,
  );
  const handoff = pdf(fixture.pdf_lines);
  writeFileSync(join(out, "preliminary-handoff.pdf"), handoff);
  const attachment = await upload(ben, "preliminary-handoff.pdf", "application/pdf", handoff);
  await api(
    ben,
    `/workspaces/${privateGroup.id}/posts`,
    { body: fixture.private_message, attachment_ids: [attachment.id], client_id: "research-private-handoff" },
    201,
  );
  await api(
    chen,
    `/workspaces/${privateGroup.id}/chat`,
    {
      body: "Received. I will repeat the reference before we share anything more widely.",
      client_id: "research-private-reply",
    },
    201,
  );
  const artwork = await browser.newPage({ viewport: { width: 1000, height: 730 } });
  await artwork.setContent(readFileSync(join(root, "fixtures/research-day/research-plan.svg"), "utf8"));
  const png = await artwork.locator("svg").screenshot({ path: join(out, "research-plan.png") });
  await artwork.close();
  await upload(
    ben,
    "research-plan.svg",
    "image/svg+xml",
    readFileSync(join(root, "fixtures/research-day/research-plan.svg")),
    422,
  );
  check(true, "raw SVG remains rejected by the application upload boundary");
  const image = await upload(ben, "research-plan.png", "image/png", png);
  await api(
    ben,
    `/workspaces/${group.id}/posts`,
    {
      body: "Working plan / controls and handoff sequence. Handwritten notes on the live board remain editable. This PNG is a reviewed reference copy of the synthetic sketch.",
      attachment_ids: [image.id],
      client_id: "research-plan-reference",
    },
    201,
  );
  const noteId = (await api(ben, "/notes")).notes[0].id;
  for (const a of [asha, people.mira, dana, admin]) {
    assert.equal((await a.ctx.request.get(origin + `/api/v1/files/${attachment.id}`)).status(), 404);
    assert.equal((await a.ctx.request.get(origin + `/api/v1/workspaces/${privateGroup.id}`)).status(), 404);
    assert.equal((await a.ctx.request.get(origin + `/api/v1/notes/${noteId}`)).status(), 404);
  }
  check(
    true,
    "private group, PDF and personal note excluded from colleagues, division steward and administrator",
  );
  for (const [a, section] of [
    [ben, "Catalysis Section"],
    [chen, "Thin Films Section"],
    [dana, "Thin Films Section"],
  ])
    assert.equal((await a.ctx.request.get(origin + `/api/v1/workspaces/${spaces[section]}`)).status(), 404);
  for (const a of Object.values(people))
    assert.equal(
      (await a.ctx.request.get(origin + `/api/v1/workspaces/${spaces["Surface Science Division"]}`)).status(),
      200,
    );
  check(true, "sibling sections remain isolated, grants flow upward to the shared division only");
  assert.equal((await chen.ctx.request.get(origin + `/api/v1/files/${attachment.id}`)).status(), 200);
  check(true, "named colleague can download the private handoff PDF");
  for (const a of Object.values(people)) {
    await view(a, group.id, "board");
    await a.page.getByText(new RegExp(`rev ${caughtUp.revision}`)).waitFor();
    await a.page.getByRole("button", { name: "Fit", exact: true }).click();
    await a.page.getByText("Saved", { exact: true }).waitFor();
  }
  // All contexts are present on the shared board before capture.
  await ben.page.getByText("Mira Sen", { exact: false }).first().waitFor();
  for (const a of Object.values(people))
    await shot(a, `board-${a.username}.png`, `${a.username}: shared five-person research board`);
  await view(chen, group.id, "chat");
  await chen.page.getByText(fixture.chat.at(-1)[1], { exact: true }).waitFor();
  await shot(chen, "group-chat.png", "Chen: cross-section research discussion");
  await view(dana, spaces["Surface Science Division"], "noticeboard");
  await dana.page.getByText("Aurora / Friday review", { exact: false }).first().waitFor();
  await shot(dana, "division-notice.png", "Dana: division-level review notice");
  await view(ben, privateGroup.id, "noticeboard");
  await ben.page.getByRole("link", { name: /preliminary-handoff.pdf/ }).waitFor();
  await shot(ben, "private-handoff.png", "Ben: private two-person group with PDF attachment");
  await view(asha, spaces["Thin Films Section"], "noticeboard");
  await shot(asha, "section-thin-films.png", "Asha: section-only preparation log");
  await view(people.mira, spaces["Catalysis Section"], "noticeboard");
  await shot(people.mira, "section-catalysis.png", "Mira: sibling-section GC queue");
  await ben.page.goto(origin + "/notes");
  await ben.page.getByText("Private: check reference drift", { exact: false }).first().waitFor();
  await shot(ben, "personal-notes.png", "Ben: owner-only reminder and note");
  check(errors.length === 0, `no browser errors or external asset requests (${errors.join(";")})`);
  writeFileSync(
    join(out, "report.json"),
    JSON.stringify(
      {
        title: fixture.title,
        checks,
        shots,
        objects: objects.length,
        group: group.id,
        privateGroup: privateGroup.id,
      },
      null,
      2,
    ),
  );
  writeFileSync(
    join(out, "index.html"),
    `<!doctype html><meta charset="utf-8"><title>LabAdda research-day simulation</title><style>body{font:16px system-ui;background:#edf1f5;margin:32px;color:#172b4d}article{background:white;padding:20px;margin:30px 0;border-radius:12px}img{width:100%;height:auto}a{color:#1565c0}</style><h1>Five researchers / one realistic working day</h1><p>Actual application screenshots. Entirely synthetic data. Private colleague attachments use a two-person group, not direct messages. Native pen strokes and editable stickies come from the saved SVG/JSON fixtures.</p>${shots.map((s) => `<article><h2>${s.caption}</h2><a href="${s.file}"><img src="${s.file}" alt="${s.caption}"></a></article>`).join("")}`,
  );
  console.log(`Research scenario: ${checks.length} checks passed; ${shots.length} screenshots at ${out}`);
} finally {
  for (const ctx of contexts) await ctx.close();
  await browser.close();
}
