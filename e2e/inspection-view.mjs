// Complements governance.mjs after operator CLI inspection of that disposable stack.
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const out = process.argv[2] ?? "/tmp/labadda-governance";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
try {
  for (const base of ["", "/labadda-staging"]) {
    const ctx = await browser.newContext({
      viewport: { width: 1400, height: 1100 },
      timezoneId: "Asia/Kolkata",
    });
    const page = await ctx.newPage();
    await page.goto("http://127.0.0.1:8080" + base + "/admin/storage");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page
      .getByRole("heading", { name: "Storage inventories, inspections and reconciliations" })
      .waitFor();
    const data = await (
      await ctx.request.get("http://127.0.0.1:8080" + base + "/api/v1/admin/storage-inspections")
    ).json();
    const receipt = data.inspections.find((r) => r.summary.scope === "database_referenced_assets");
    assert.ok(receipt);
    const checked = receipt.summary.checked_assets;
    assert.ok(checked > 0);
    assert.equal(receipt.summary.issue_count, 0);
    await page
      .getByText(new RegExp(`completed · ${checked} asset rows checked · 0 issues`))
      .first()
      .waitFor();
    const summary = receipt.summary;
    assert.equal(
      summary.preview_integrity,
      summary.selected_previews > 0 && summary.unknown_previews === 0 ? "verified_selected" : "unverified",
    );
    await page
      .getByText(new RegExp(`Preview checks: ${summary.verified_previews} verified`))
      .first()
      .waitFor();
    assert.equal(receipt.summary.complete_for_enforcement, false);
    await page.screenshot({ path: out + (base ? "/admin-prefix.png" : "/admin-root.png"), fullPage: true });
    console.log("PASS " + base + ": original inspection receipt shown without enforcement authority");
    await ctx.close();
  }
} finally {
  await browser.close();
}
