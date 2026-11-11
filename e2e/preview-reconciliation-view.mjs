// Run after host-operator dry-runs on both disposable proxy-stack databases.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const output = process.argv[2] ?? "/tmp/labadda-preview-reconciliation";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
try {
  for (const base of ["", "/labadda-staging"]) {
    const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } }),
      page = await ctx.newPage();
    await page.goto("http://127.0.0.1:8080" + base + "/admin");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Sign out" }).waitFor();
    const data = await (
      await ctx.request.get("http://127.0.0.1:8080" + base + "/api/v1/admin/storage-inspections")
    ).json();
    const receipt = data.inspections.find((r) => r.summary.scope === "preview_metadata_reconciliation");
    assert.ok(receipt);
    assert.equal(receipt.summary.mode, "dry_run");
    assert.equal(receipt.summary.applied_count, 0);
    assert.equal(receipt.summary.complete_for_enforcement, false);
    const line = page.getByText(
      new RegExp(
        `Preview reconciliation Dry run: ${receipt.summary.candidate_count} candidates · 0 metadata updates`,
      ),
    );
    await line.first().waitFor();
    checks++;
    console.log("PASS " + base + ": actual dry-run receipt shown separately from verification");
    assert.equal(await page.getByRole("button", { name: /Apply preview/ }).count(), 0);
    checks++;
    console.log("PASS " + base + ": metadata receipt grants no web application action");
    await line.first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: output + (base ? "/dry-run-prefix.png" : "/dry-run-root.png") });
    await ctx.close();
  }
  console.log(`${checks} preview reconciliation browser checks passed`);
} finally {
  await browser.close();
}
