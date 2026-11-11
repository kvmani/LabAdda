// Run after inventory-storage on both disposable proxy-stack databases.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const output = process.argv[2] ?? "/tmp/labadda-storage-inventory";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
let checks = 0;
function check(ok, label) {
  assert.ok(ok, label);
  checks++;
  console.log("PASS " + label);
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:8080" + base + "/admin");
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.getByRole("button", { name: "Sign out" }).waitFor();
    const result = await (
      await context.request.get("http://127.0.0.1:8080" + base + "/api/v1/admin/storage-inspections")
    ).json();
    const receipt = result.inspections.find((r) => r.summary.scope === "asset_directory_inventory");
    check(
      receipt && !receipt.summary.deletion_authorized && !receipt.summary.complete_for_enforcement,
      base + " actual bounded receipt",
    );
    const inventory = page.getByText("Asset-directory inventory", { exact: true });
    await inventory.first().waitFor();
    check(
      (await page
        .getByText(
          new RegExp(
            `Unreferenced candidates: ${receipt.summary.classes.unreferenced_candidate.entries} entries`,
          ),
        )
        .count()) > 0,
      base + " candidate aggregate visible",
    );
    check((await page.getByText(/not safe to delete/).count()) > 0, base + " uncertainty visible");
    check(!JSON.stringify(result).includes("private-fixture-label"), base + " private file names absent");
    check(
      (await page.getByRole("button", { name: /delete.*candidate|purge|apply.*inventory/i }).count()) === 0,
      base + " no mutation control",
    );
    for (const width of [1400, 390]) {
      await page.setViewportSize({ width, height: 1100 });
      await inventory.first().scrollIntoViewIfNeeded();
      await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
      const violations = await page.evaluate(async () =>
        (
          await window.axe.run(document, {
            runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
          })
        ).violations.map((v) => v.id),
      );
      check(violations.length === 0, base + " axe " + width + ": " + violations.join(","));
      check(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        base + " no overflow " + width,
      );
      await page.screenshot({ path: output + "/" + (base ? "prefix" : "root") + "-" + width + ".png" });
    }
    await context.close();
  }
  console.log(`${checks} inventory browser checks passed`);
} finally {
  await browser.close();
}
