// T17 / DL-07 browser evidence: text and whiteboard logical charges at root and prefix,
// an unreconciled historical board reported as a lower bound, and an actual operator
// reconciliation receipt. Run against a FRESH disposable `scripts/proxy-stack.sh start` stack:
// it rewrites board ledger rows in the e2e databases to simulate pre-migration history.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const { chromium } = createRequire(import.meta.url)("playwright");
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const origin = process.argv[2] ?? "http://127.0.0.1:8080";
if (!["127.0.0.1", "localhost"].includes(new URL(origin).hostname))
  throw Error("Use a local disposable test stack");
const out = process.argv[3] ?? "/tmp/labadda-content-charges";
mkdirSync(out, { recursive: true });
const PG = process.env.LABADDA_PG ?? "postgresql+psycopg://labadda:labadda-dev@localhost:5432";
const INSTANCES = [
  ["", "labadda_e2e_root"],
  ["/labadda-staging", "labadda_e2e_prefix"],
];
const TEXT = "Ångström µm 🧪 薄膜"; // 16 characters, 26 UTF-8 bytes
const password = process.env.LABADDA_FIXTURE_PASSWORD ?? "fixture-pass-123";
const browser = await chromium.launch(
  process.env.LABADDA_CHROMIUM ? { executablePath: process.env.LABADDA_CHROMIUM } : {},
);
let checks = 0;
function check(value, text) {
  assert.ok(value, text);
  checks++;
  console.log("PASS " + text);
}

async function signIn(base, name) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1100 } });
  const page = await ctx.newPage();
  await page.goto(origin + base + "/");
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: /^Account menu for / }).waitFor();
  return { ctx, page };
}

function chargeRow(page, label) {
  return page.getByRole("row", { name: new RegExp("^" + label) });
}

async function liveCell(page, label) {
  return (await chargeRow(page, label).getByRole("cell").first().innerText()).trim();
}

function cli(db, args) {
  const env = { ...process.env, LABADDA_DATABASE_URL: `${PG}/${db}`, LABADDA_ENV: "test" };
  try {
    return JSON.parse(
      execFileSync(join(ROOT, ".venv/bin/labadda"), ["reconcile-charges", ...args], {
        env,
        encoding: "utf8",
      }),
    );
  } catch (err) {
    if (err.status === 2 && err.stdout) return JSON.parse(err.stdout); // drift found: still a valid receipt
    throw err;
  }
}

function sql(db, statement) {
  execFileSync("psql", [`postgresql://labadda:labadda-dev@localhost:5432/${db}`, "-qc", statement], {
    env: { ...process.env, PGPASSWORD: "labadda-dev" },
  });
}

try {
  for (const [base, db] of INSTANCES) {
    const tag = base || "root";
    const bharat = await signIn(base, "bharat");
    const workspaces = await (await bharat.ctx.request.get(origin + base + "/api/v1/workspaces")).json();
    const section = workspaces.workspaces.find((w) => w.name === "Thin Films Section").id;
    await bharat.page.goto(origin + base + `/w/${section}/noticeboard`);
    await bharat.page.getByLabel("Message").fill(TEXT);
    await bharat.page.getByRole("button", { name: "Post", exact: true }).click();
    await bharat.page.getByRole("status").filter({ hasText: "Posted" }).waitFor();
    await bharat.page.goto(origin + base + `/w/${section}/board`);
    await bharat.page.getByRole("status").filter({ hasText: "Saved" }).waitFor();
    const box = await bharat.page.locator(".canvas").boundingBox();
    await bharat.page.mouse.move(box.x + 120, box.y + 120);
    await bharat.page.mouse.down();
    for (let i = 1; i <= 6; i++) await bharat.page.mouse.move(box.x + 120 + i * 20, box.y + 120 + i * 9);
    await bharat.page.mouse.up();
    await bharat.page.getByRole("status").filter({ hasText: "Saved" }).waitFor();

    await bharat.page.goto(origin + base + "/usage");
    await chargeRow(bharat.page, "Posts and replies").waitFor();
    check(
      (await liveCell(bharat.page, "Posts and replies")) === "26 B · 1 item",
      `${tag}: a 16-character post is charged as its 26 UTF-8 bytes`,
    );
    check(
      /· 1 item$/.test(await liveCell(bharat.page, "Whiteboard objects")),
      `${tag}: the drawn stroke is charged to its author`,
    );
    check(
      (await bharat.page.getByText(/lower bound/).count()) === 0,
      `${tag}: new boards report complete charges`,
    );
    await bharat.page.screenshot({ path: `${out}/${tag.replace("/", "")}-user-usage.png`, fullPage: true });

    const chitra = await signIn(base, "chitra");
    await chitra.page.goto(origin + base + "/usage");
    await chargeRow(chitra.page, "Posts and replies").waitFor();
    check(
      (await liveCell(chitra.page, "Posts and replies")) === "0 B · 0 items",
      `${tag}: another user sees only their own charges`,
    );
    check((await chitra.page.content()).includes(TEXT) === false, `${tag}: usage pages never show content`);

    // Simulate a board whose history predates the ledger.
    sql(
      db,
      "update boards set charges_epoch = null; delete from content_charges where item_type = 'board_object'",
    );
    const admin = await signIn(base, "admin");
    await admin.page.goto(origin + base + "/admin/storage");
    await admin.page.getByText(/Whiteboard totals are a lower bound: 1 board/).waitFor();
    check(true, `${tag}: an unreconciled historical board is reported as a lower bound, not zero`);
    await admin.page.screenshot({
      path: `${out}/${tag.replace("/", "")}-admin-incomplete.png`,
      fullPage: true,
    });

    const dry = cli(db, []);
    check(
      dry.status === "completed" &&
        dry.summary.boards_to_complete === 1 &&
        dry.summary.issue_counts.missing_charge === 1,
      `${tag}: operator dry run finds the missing board charge without changing it`,
    );
    // Test stack only: no concurrent writers are running during this step.
    const applied = cli(db, ["--apply", "--writers-quiesced", "--expected-plan", dry.summary.plan_digest]);
    check(
      applied.status === "completed" && applied.summary.applied_count === 2,
      `${tag}: reviewed plan applied`,
    );
    await admin.page.reload();
    await admin.page
      .getByText(/Text\/whiteboard charge reconciliation Apply/)
      .first()
      .waitFor();
    check(
      (await admin.page.getByText(/lower bound/).count()) === 0,
      `${tag}: admin view is complete after reconciliation`,
    );
    check(
      (await admin.page.getByText(/Text\/whiteboard charge reconciliation Dry run/).count()) >= 1,
      `${tag}: dry-run and apply receipts are both listed`,
    );
    await admin.page.screenshot({
      path: `${out}/${tag.replace("/", "")}-admin-reconciled.png`,
      fullPage: true,
    });
    await bharat.page.reload();
    await chargeRow(bharat.page, "Whiteboard objects")
      .getByText(/· 1 item/)
      .waitFor();
    check(true, `${tag}: the author's board charge is restored by reconciliation`);
    for (const s of [bharat, chitra, admin]) await s.ctx.close();
  }
  console.log(`${checks} content-charge browser checks passed. Screenshots: ${out}`);
} finally {
  await browser.close();
}
