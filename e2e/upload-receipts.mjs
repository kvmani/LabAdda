// Run against a fresh disposable proxy stack; this removes Ben's section grant.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
const origin = process.argv[2] ?? "http://127.0.0.1:8080";
if (!["127.0.0.1", "localhost"].includes(new URL(origin).hostname))
  throw Error("Use a local disposable test stack");
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let passed = 0;
function check(value, label) {
  assert.ok(value, label);
  passed++;
  console.log("PASS " + label);
}
async function login(base, name) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Sign out" }).waitFor();
  const session = await (await ctx.request.get(origin + base + "/api/v1/auth/session")).json();
  return { ctx, page, session };
}
async function send(page, api, csrf, key, extra = "") {
  return page.evaluate(
    async ({ api, csrf, key, extra }) => {
      const form = new FormData();
      form.append(
        "file",
        new Blob(["%PDF-1.4\nBrowser receipt fixture\n%%EOF" + extra], { type: "application/pdf" }),
        "receipt-fixture.pdf",
      );
      try {
        const result = await fetch(api + "/uploads", {
          method: "POST",
          headers: { "X-CSRF-Token": csrf, "Idempotency-Key": key },
          body: form,
        });
        return { status: result.status, data: await result.json() };
      } catch {
        return { transportFailed: true };
      }
    },
    { api, csrf, key, extra },
  );
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const ben = await login(base, "ben"),
      chen = await login(base, "chen"),
      admin = await login(base, "admin");
    const api = origin + base + "/api/v1",
      key = "browser-lost-reply-01";
    const before = await (await ben.ctx.request.get(api + "/usage")).json();
    await ben.page.route(
      api + "/uploads",
      async (route) => {
        const committed = await route.fetch();
        assert.equal(committed.status(), 201);
        await route.abort("failed"); // Server committed; this browser loses the response.
      },
      { times: 1 },
    );
    const lost = await send(ben.page, api, ben.session.csrf_token, key);
    check(lost.transportFailed, base + ": committed upload response lost in transport");
    const status = await ben.ctx.request.get(api + "/uploads/requests/" + key);
    const record = await status.json();
    check(
      status.status() === 200 && record.state === "complete",
      base + ": owner recovers completed receipt",
    );
    check(status.headers()["cache-control"].includes("no-store"), base + ": receipt is not cacheable");
    const replay = await send(ben.page, api, ben.session.csrf_token, key);
    check(
      replay.status === 201 && replay.data.id === record.asset.id,
      base + ": same-key browser retry returns original file",
    );
    const after = await (await ben.ctx.request.get(api + "/usage")).json();
    check(
      after.measurement.tracked_files === before.measurement.tracked_files + 1 &&
        after.measurement.tracked_original_bytes ===
          before.measurement.tracked_original_bytes + record.asset.size &&
        after.measurement.pending_upload_original_bytes === 0,
      base + ": retry neither duplicates original nor charges twice",
    );
    const changed = await send(ben.page, api, ben.session.csrf_token, key, "\nchanged");
    check(
      changed.status === 409 && changed.data.error.code === "upload_key_reused",
      base + ": changed content rejected",
    );
    for (const [name, actor] of [
      ["sibling", chen],
      ["administrator", admin],
    ]) {
      check(
        (await actor.ctx.request.get(api + "/uploads/requests/" + key)).status() === 404,
        base + ": " + name + " cannot discover another user receipt",
      );
    }
    const spaces = await (await ben.ctx.request.get(api + "/workspaces")).json();
    const section = spaces.workspaces.find((w) => w.name === "Thin Films Section");
    assert.ok(section);
    const posted = await ben.ctx.request.post(api + "/workspaces/" + section.id + "/posts", {
      headers: { "X-CSRF-Token": ben.session.csrf_token },
      data: { body: "Synthetic receipt browser attachment", attachment_ids: [record.asset.id] },
    });
    assert.equal(posted.status(), 201);
    const users = await (await admin.ctx.request.get(api + "/admin/users")).json();
    const user = users.users.find((u) => u.username === "ben");
    const revoked = await admin.ctx.request.delete(
      api + "/admin/workspaces/" + section.id + "/memberships/" + user.id,
      { headers: { "X-CSRF-Token": admin.session.csrf_token } },
    );
    assert.equal(revoked.status(), 200);
    check(
      (await ben.ctx.request.get(api + "/uploads/requests/" + key)).status() === 404,
      base + ": status rechecks revoked content access",
    );
    check(
      (await send(ben.page, api, ben.session.csrf_token, key)).status === 404,
      base + ": replay rechecks revoked content access",
    );
    for (const actor of [ben, chen, admin]) await actor.ctx.close();
  }
  console.log(`${passed} upload receipt browser checks passed`);
} finally {
  await browser.close();
}
