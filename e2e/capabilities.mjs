// Requires fresh proxy-stack fixtures; may follow governance.mjs.
import { mkdirSync } from "node:fs";
import { bases, fixturePassword, origin, startHarness } from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/labadda-capabilities";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness({ timezoneId: "Asia/Kolkata" });
const { check, login } = harness;

const statusOf = async (user, base, path) => (await user.ctx.request.get(origin + base + path)).status();

async function denyThenGrantObserver(admin, ben, base) {
  await ben.page.goto(origin + base + "/operations");
  await ben.page.waitForURL((url) => !/\/(admin|operations)(\/|$)/.test(url.pathname));
  check(true, base + ": observer access starts denied");
  const page = admin.page;
  await page.goto(origin + base + "/admin/settings");
  await page.getByLabel("Operational reader account").selectOption({ label: "ben" });
  await page.getByLabel("Access change reason").fill("Synthetic storage observation walkthrough");
  await page.getByLabel("Confirm administrator password").fill("incorrect-fixture-password");
  await page.getByRole("button", { name: "Grant operational read access" }).click();
  await page.getByRole("alert").filter({ hasText: "Password confirmation failed" }).waitFor();
  check(
    (await statusOf(ben, base, "/api/v1/admin/usage")) === 403,
    base + ": incorrect password grants nothing",
  );
  await page.getByLabel("Confirm administrator password").fill(fixturePassword);
  await page.getByRole("button", { name: "Grant operational read access" }).click();
  await page.getByText("Time-limited operational read access granted.", { exact: true }).waitFor();
  check(
    (await page.getByLabel("Confirm administrator password").inputValue()) === "",
    base + ": password cleared after operation",
  );
}

async function checkObserverReadsAndIsLimited(ben, base) {
  await ben.page.goto(origin + base + "/operations");
  await ben.page.getByRole("heading", { name: "Partial site measurement" }).waitFor();
  await ben.page.screenshot({
    path: outputDir + (base ? "/observer-prefix.png" : "/observer-root.png"),
    fullPage: true,
  });
  check(true, base + ": granted observer reads operational metadata");
  const users = await statusOf(ben, base, "/api/v1/admin/users");
  const drafts = await statusOf(ben, base, "/api/v1/admin/policy-drafts");
  check(users === 403 && drafts === 403, base + ": observer cannot administer identities or policies");
}

async function revokeAndCheckRefresh(admin, ben, base) {
  await admin.page.getByLabel("Confirm administrator password").fill(fixturePassword);
  await admin.page.getByRole("button", { name: "Revoke selected account", exact: true }).click();
  await admin.page.getByText("Operational access revoked.", { exact: true }).waitFor();
  await ben.page.getByRole("button", { name: "Refresh operational observations" }).click();
  await ben.page.getByRole("alert").filter({ hasText: "Operational read access is required" }).waitFor();
  const measurements = await ben.page.getByRole("heading", { name: "Partial site measurement" }).count();
  check(measurements === 0, base + ": revoked refresh clears measurement and is refused");
}

try {
  for (const base of bases) {
    const admin = await login(base, "admin");
    const ben = await login(base, "ben");
    await denyThenGrantObserver(admin, ben, base);
    await checkObserverReadsAndIsLimited(ben, base);
    await revokeAndCheckRefresh(admin, ben, base);
    await ben.ctx.close();
    await admin.ctx.close();
  }
  console.log(`${harness.checks()} capability browser checks passed`);
} finally {
  await harness.close();
}
