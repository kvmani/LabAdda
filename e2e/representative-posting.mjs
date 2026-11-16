// Contribution permissions and delegation controls through the real root/prefix deployments.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const axe = require("../frontend/node_modules/axe-core");
const origin = process.env.LABADDA_E2E_ORIGIN ?? "http://127.0.0.1:8080";
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
function check(value, label) {
  if (!value) throw new Error(label);
  console.log(`PASS ${label}`);
}
async function login(base, username) {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  const page = await context.newPage();
  await page.goto(`${origin}${base}/login`);
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { context, page };
}
async function get(page, base, path) {
  return page.evaluate(async ({ base, path }) => (await fetch(`${base}/api/v1${path}`)).json(), {
    base,
    path,
  });
}
try {
  for (const base of ["", "/labadda-staging"]) {
    const member = await login(base, "bharat");
    const steward = await login(base, "asha");
    const list = await get(member.page, base, "/workspaces");
    const division = list.workspaces.find((unit) => unit.name === "Surface Engineering Division");
    const section = list.workspaces.find((unit) => unit.name === "Thin Films Section");
    await member.page.goto(`${origin}${base}/w/${division.id}/board`);
    await member.page
      .getByText(/Contributions are limited to unit representatives/)
      .first()
      .waitFor();
    check(
      (await member.page.getByRole("button", { name: "✏️ Draw", exact: true }).count()) === 0,
      "ancestor board hides drawing controls",
    );
    await member.page.goto(`${origin}${base}/w/${division.id}/chat`);
    check(
      (await member.page.getByRole("button", { name: "Send", exact: true }).count()) === 0,
      "ancestor chat hides sending controls",
    );
    await steward.page.goto(`${origin}${base}/w/${section.id}/members`);
    await steward.page
      .getByLabel("Reason for appointment or revocation")
      .fill("Represent section during pilot");
    await steward.page
      .getByLabel("Representative", { exact: true })
      .selectOption({ label: "Bharat Kulkarni" });
    await steward.page.getByRole("button", { name: "Appoint representative", exact: true }).click();
    await steward.page
      .getByRole("dialog")
      .getByRole("button", { name: "Appoint representative", exact: true })
      .click();
    await steward.page.getByRole("dialog").waitFor({ state: "hidden" });
    await member.page.getByLabel("Message Surface Engineering Division", { exact: true }).waitFor();
    check(true, "delegation enables contribution in an existing browser session");
    await steward.page.getByLabel("Reason for appointment or revocation").fill("Pilot representation ended");
    await steward.page.getByRole("button", { name: "Revoke representation", exact: true }).click();
    await steward.page
      .getByRole("dialog")
      .getByRole("button", { name: "Revoke representation", exact: true })
      .click();
    await steward.page.getByRole("dialog").waitFor({ state: "hidden" });
    await member.page
      .getByLabel("Message Surface Engineering Division", { exact: true })
      .waitFor({ state: "hidden" });
    check(true, "revocation hides contribution controls without reloading");
    await member.page.goto(`${origin}${base}/w/${section.id}/members`);
    check(
      (await member.page.getByRole("button", { name: "Appoint representative", exact: true }).count()) === 0,
      "ordinary members cannot manage representation",
    );
    for (const width of [1400, 390]) {
      await steward.page.setViewportSize({ width, height: 1000 });
      await steward.page.addScriptTag({ content: axe.source });
      const failures = await steward.page.evaluate(
        async () =>
          (await axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] } })).violations,
      );
      check(failures.length === 0, `representative management accessibility at ${width}px`);
    }
    await member.context.close();
    await steward.context.close();
    console.log(`PASS ${base || "root"}: representative posting flow complete`);
  }
} finally {
  await browser.close();
}
