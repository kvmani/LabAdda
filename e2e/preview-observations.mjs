// Real browser metadata views after new image creation. Local synthetic stack only.
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { bases, origin, startHarness } from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/labadda-preview-observations";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness();
const { check, login } = harness;

const tinyPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAHUlEQVR4nGP4z8BAEhrVMKphVMOohlENIxoGAAD4/H8BWrLzvAAAAABJRU5ErkJggg==",
  "base64",
);

const fetchJson = async (user, url) => (await user.ctx.request.get(url)).json();

async function uploadPrivateImage(ben, api) {
  const response = await ben.ctx.request.post(api + "/uploads", {
    headers: { "X-CSRF-Token": ben.session.csrf_token },
    multipart: { file: { name: "private-derivative-fixture.png", mimeType: "image/png", buffer: tinyPng } },
  });
  assert.equal(response.status(), 201);
  return response.json();
}

function checkMeasurements(before, after, previewBytes, base) {
  check(
    after.measurement.tracked_preview_bytes === before.measurement.tracked_preview_bytes + previewBytes,
    base + ": recorded preview bytes match stored raster",
  );
  check(
    after.measurement.unknown_preview_files === before.measurement.unknown_preview_files,
    base + ": new preview does not conceal unknown history",
  );
  check(
    after.runtime_limit.bytes === before.runtime_limit.bytes &&
      after.measurement.complete_for_enforcement === false,
    base + ": pilot allowance remains unchanged and measurement partial",
  );
}

async function checkUserAndAdminViews(ben, admin, base) {
  await ben.page.goto(origin + base + "/usage");
  await ben.page.getByText("Previews with recorded measurements", { exact: true }).waitFor();
  check(
    await ben.page.getByText("Previews with unknown measurements", { exact: true }).isVisible(),
    base + ": user sees measured and unknown categories",
  );
  await ben.page.screenshot({
    path: outputDir + (base ? "/user-prefix.png" : "/user-root.png"),
    fullPage: true,
  });
  await admin.page.goto(origin + base + "/admin/storage");
  await admin.page.getByText("Previews with recorded measurements", { exact: true }).waitFor();
  const adminText = await admin.page.locator("body").innerText();
  check(
    !adminText.includes("private-derivative-fixture"),
    base + ": admin observation does not expose private filename",
  );
  await admin.page.screenshot({
    path: outputDir + (base ? "/admin-prefix.png" : "/admin-root.png"),
    fullPage: true,
  });
}

try {
  for (const base of bases) {
    const ben = await login(base, "ben");
    const admin = await login(base, "admin");
    const api = origin + base + "/api/v1";
    const before = await fetchJson(ben, api + "/usage");
    const asset = await uploadPrivateImage(ben, api);
    const preview = await (await ben.ctx.request.get(origin + asset.preview_url)).body();
    const after = await fetchJson(ben, api + "/usage");
    checkMeasurements(before, after, preview.length, base);
    await checkUserAndAdminViews(ben, admin, base);
    await ben.ctx.close();
    await admin.ctx.close();
  }
  console.log(`${harness.checks()} preview observation browser checks passed`);
} finally {
  await harness.close();
}
