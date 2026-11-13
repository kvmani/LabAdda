// P6x Excel staff import: template, problems, report, apply, slips, mixed-depth chart, forced password change.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const origin = "http://127.0.0.1:8080";
const output = process.argv[2] ?? "/tmp/labadda-people-import-excel";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.LABADDA_CHROMIUM ?? "/usr/bin/chromium",
});
const SHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const FIRST_PASSWORD = "Sunrise-Lab-2027";
let checks = 0;
function check(condition, label) {
  assert.ok(condition, label);
  console.log("PASS " + label);
  checks++;
}
async function login(base, username, password = "fixture-pass-123") {
  const context = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await context.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  return { context, page };
}
async function audit(page, width, label) {
  await page.setViewportSize({ width, height: 1100 });
  await page.addScriptTag({ path: require.resolve("../frontend/node_modules/axe-core/axe.min.js") });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      })
    ).violations.map((item) => item.id),
  );
  check(violations.length === 0, `${label} accessibility ${width}: ${violations}`);
  await page.setViewportSize({ width: 1400, height: 1100 });
}
/** The server's own writer builds the workbook, so the file is the template filled in. */
function workbook(rows) {
  const code =
    "import sys,json,base64\nfrom labadda.changes import xlsx\n" +
    "sys.stdout.write(base64.b64encode(xlsx.write_rows(json.load(sys.stdin))).decode())";
  const out = execFileSync(`${root}/.venv/bin/python`, ["-c", code], {
    input: JSON.stringify(rows),
    env: { ...process.env, PYTHONPATH: `${root}/backend` },
  });
  return Buffer.from(out.toString(), "base64");
}
const HEAD = [
  "full_name",
  "division",
  "section",
  "Emp No",
  "email",
  "Extension",
  "Group",
  "Residence Phone",
  "username",
  "Password",
  "is_active",
  "role",
];
const person = (name, user, no, group, division = "", section = "", more = {}) => [
  name,
  division,
  section,
  no,
  "",
  more.ext ?? "",
  group,
  "",
  user,
  more.password ?? "",
  "",
  more.role ?? "",
];
const GROUP = "Polymer Group";
const PEOPLE = [
  person("Ananya Iyer", "ananya.iyer", "00201", GROUP, "Resin Division", "Curing Section", { ext: "4417" }),
  person("Rohit Deshpande", "rohit.deshpande", "00202", GROUP, "Resin Division", "Curing Section"),
  person("Meera Nair", "meera.nair", "00203", GROUP, "Resin Division", "Curing Section"),
  person("Kabir Menon", "kabir.menon", "00204", GROUP, "Resin Division", "Adhesives Section"),
  person("Latha Pillai", "latha.pillai", "00205", GROUP, "Resin Division", "Adhesives Section"),
  person("Dev Kapoor", "dev.kapoor", "00206", GROUP, "Resin Division"),
  person("Isha Rao", "isha.rao", "00207", GROUP, "Resin Division"),
  person("Om Bhatt", "om.bhatt", "00208", GROUP, "", "Rheology Section"),
  person("Zoya Khan", "zoya.khan", "00209", GROUP, "", "Rheology Section"),
  person("Esha Roy", "esha.roy", "00210", GROUP, "", "Rheology Section"),
  person("Farhan Ali", "farhan.ali", "00211", GROUP),
  person("Tara Joshi", "tara.joshi", "00212", GROUP, "Fibre Division", "Spinning Section"),
  person("Uma Reddy", "uma.reddy", "00213", GROUP, "Fibre Division", "Spinning Section", {
    password: FIRST_PASSWORD,
  }),
  person("Vikram Sethi", "vikram.sethi", "00214", GROUP, "Fibre Division"),
  person("Priya Kulkarni", "priya.kulkarni", "00215", GROUP, "Fibre Division", "", { role: "admin" }),
];
const slug = (base) => base.replaceAll("/", "-") || "-root";

async function openDialog(page, base) {
  await page.goto(origin + base + "/admin/people");
  await page.getByRole("button", { name: "Import from Excel", exact: true }).click();
  return page.getByRole("dialog", { name: "Import staff from Excel", exact: true });
}
const upload = (dialog, name, buffer, mimeType = SHEET) =>
  dialog.getByLabel("Staff sheet file").setInputFiles({ name, mimeType, buffer });

async function importWorkbook(page, base) {
  const dialog = await openDialog(page, base);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    dialog.getByRole("button", { name: "Download the Excel template", exact: true }).click(),
  ]);
  check(download.suggestedFilename() === "staff-import-template.xlsx", base + " template downloads as .xlsx");
  check(
    readFileSync(await download.path())
      .subarray(0, 2)
      .toString() === "PK",
    base + " template is a workbook",
  );
  await upload(dialog, "people.pdf", Buffer.from("x"), "application/pdf");
  check(
    await dialog
      .getByRole("alert")
      .getByText(/Choose an Excel workbook/)
      .isVisible(),
    base + " wrong type refused",
  );
  const broken = PEOPLE.map((row) => [...row]);
  broken[2][3] = "";
  await upload(dialog, "broken.xlsx", workbook([HEAD, ...broken]));
  await dialog.getByText(/Emp No is required/).waitFor();
  check(
    (await dialog.getByRole("button", { name: /^Add \d+ people$/ }).count()) === 0,
    base + " a row with a problem blocks the whole file",
  );
  await upload(dialog, "staff.xlsx", workbook([HEAD, ...PEOPLE]));
  const report = dialog.getByRole("region", { name: "Import report" });
  await report.waitFor();
  const summary = await report.innerText();
  check(
    /15 people will be added and 7 units will be created/.test(summary),
    base + " report counts (" + summary.split("\n")[0] + ")",
  );
  check(
    await report.getByText(/Priya Kulkarni will become an administrator/).isVisible(),
    base + " administrator warning",
  );
  check(
    await report.getByText("Create the group Polymer Group", { exact: false }).isVisible(),
    base + " group will be created",
  );
  check(
    await report.getByText("Create the section Rheology Section", { exact: false }).isVisible(),
    base + " direct section will be created",
  );
  await page.screenshot({ path: `${output}/report${slug(base)}.png` });
  await audit(page, 1400, base + " excel report");
  await report.getByLabel(/^Reason for this change/).fill("Pilot onboarding");
  await dialog.getByRole("button", { name: "Add 15 people", exact: true }).click();
  await dialog.getByText("15 people were added.").waitFor();
  check(
    await dialog.getByRole("region", { name: "Activation slip for Ananya Iyer" }).isVisible(),
    base + " slip for a person without a password",
  );
  check(
    (await dialog.getByRole("region", { name: "Activation slip for Uma Reddy" }).count()) === 0,
    base + " no slip for a first password",
  );
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("button", { name: "View profile for Farhan Ali" }).waitFor();
  check(true, base + " group-level person appears in the list");
}

async function chart(page, base) {
  await page.goto(origin + base + "/admin/org");
  const tree = page.getByRole("tree", { name: "Organisation units" });
  await tree.waitFor();
  const labels = await tree
    .getByRole("treeitem")
    .evaluateAll((items) => items.map((i) => i.getAttribute("aria-label")));
  const has = (text) => labels.some((label) => label?.includes(text));
  check(has("Polymer Group, Group"), base + " chart names the group level");
  check(
    has("Resin Division, Division") && has("Curing Section, Section"),
    base + " chart names division and section levels",
  );
  check(has("Rheology Section, Section"), base + " section directly under the group is in the chart");
  const direct = tree.getByRole("treeitem", { name: /Rheology Section/ });
  const nested = tree.getByRole("treeitem", { name: /Curing Section/ });
  check(
    (await direct.getAttribute("aria-level")) === "3" && (await nested.getAttribute("aria-level")) === "4",
    base + " sections at different depths sit under the same group",
  );
  await page.screenshot({ path: `${output}/chart${slug(base)}.png` });
  await audit(page, 1400, base + " mixed-depth chart");
  await direct.click();
  await page.getByRole("heading", { name: "Rheology Section", exact: true }).waitFor();
  check(
    await page.getByText("Section", { exact: true }).first().isVisible(),
    base + " unit panel shows the level",
  );
  const listed = await page
    .getByText("Om Bhatt")
    .first()
    .waitFor({ timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  check(listed, base + " unit panel lists its people");
  await tree.getByRole("treeitem", { name: /Polymer Group/ }).focus();
  await page.keyboard.press(" ");
  check(
    (await tree.getByRole("treeitem", { name: /Curing Section/ }).count()) === 0,
    base + " collapsing the group hides every depth below it",
  );
  await page.keyboard.press(" ");
  await tree.getByRole("treeitem", { name: /Curing Section/ }).waitFor();
  check(true, base + " expanding restores them");
  await page.getByRole("searchbox").first().fill("Spinning");
  await page
    .getByText(/Spinning Section/)
    .first()
    .waitFor();
  check(true, base + " search finds a deep unit");
}

async function profile(page, base) {
  await page.goto(origin + base + "/admin/people?q=Ananya");
  await page.getByRole("button", { name: "View profile for Ananya Iyer" }).click();
  await page.getByText("ananya.iyer@domain.in").waitFor();
  check(await page.getByText("4417").first().isVisible(), base + " profile shows email and extension");
}

async function firstPassword(base) {
  const uma = await login(base, "uma.reddy", FIRST_PASSWORD);
  try {
    const heading = uma.page.getByRole("heading", { name: "Choose your own password", exact: true });
    await heading.waitFor();
    check(true, base + " first sign-in goes straight to the password change");
    await uma.page.getByLabel("Current password").fill(FIRST_PASSWORD);
    await uma.page.getByLabel(/^New password/).fill("Fresh-Start-9876");
    await uma.page.getByLabel("Repeat new password").fill("Fresh-Start-9876");
    await uma.page.getByRole("button", { name: "Change password", exact: true }).click();
    await uma.page.getByRole("button", { name: /^Account menu for / }).waitFor();
    check(true, base + " after changing it the workspace opens");
  } finally {
    await uma.context.close();
  }
}

async function denied(base) {
  const bharat = await login(base, "bharat");
  try {
    await bharat.page.getByRole("button", { name: /^Account menu for / }).waitFor();
    const endpoint = origin + base + "/api/v1";
    const session = await (await bharat.context.request.get(endpoint + "/auth/session")).json();
    const post = await bharat.context.request.post(endpoint + "/admin/changes/import/staff/preview", {
      headers: { "X-CSRF-Token": session.csrf_token, "Content-Type": SHEET },
      data: workbook([HEAD, PEOPLE[0]]),
    });
    check(post.status() === 403, base + " member cannot use the Excel import API");
  } finally {
    await bharat.context.close();
  }
}

try {
  for (const base of ["", "/labadda-staging"]) {
    const admin = await login(base, "admin");
    try {
      await admin.page.getByRole("button", { name: /^Account menu for / }).waitFor();
      await importWorkbook(admin.page, base);
      await chart(admin.page, base);
      await profile(admin.page, base);
    } finally {
      await admin.context.close();
    }
    await firstPassword(base);
    await denied(base);
  }
  console.log(`${checks} Excel staff import browser checks passed`);
} finally {
  await browser.close();
}
