import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import {
  axeViolations,
  bases,
  call,
  hasNoSideScroll,
  loseNextResponse,
  origin,
  startHarness,
} from "./lib/harness.mjs";

const outputDir = process.argv[2] ?? "/tmp/c4-collaboration";
mkdirSync(outputDir, { recursive: true });

const harness = await startHarness({ timezoneId: "Asia/Kolkata" });
const { check, login } = harness;
const screenshots = [];
const pdf = Buffer.from("%PDF-1.4\nSynthetic instrument handoff\n%%EOF");
const peopleNames = ["asha", "bharat", "chitra", "mira", "deepa"];
const ideas = [
  "Asha: retain a witness coupon.",
  "Bharat: sample IDs mapped to run IDs.",
  "Chitra: include GC blanks and three replicates.",
  "Mira: cap transfer before XPS.",
  "Deepa: review uncertainty at the division gate.",
];
const stickyColors = ["#fff59d", "#b3e5fc", "#ffccbc", "#c8e6c9", "#fff59d"];

const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const labelled = (scope, label) => scope.getByLabel(label, { exact: true });

async function takeScreenshot(user, base, suffix, label) {
  const file = (base ? "prefix" : "root") + suffix;
  await user.page.screenshot({ path: outputDir + "/" + file, fullPage: true });
  screenshots.push({ file, label });
}

async function activateMira(admin) {
  const created = await call(admin, "/admin/users", { username: "mira", display_name: "Mira Sen" });
  const fresh = await harness.browser.newContext();
  const activation = await fresh.request.post(admin.api + "/auth/activate", {
    data: { token: created.activation_token, password: "fixture-pass-123" },
  });
  assert.equal(activation.status(), 200);
  await fresh.close();
  return created;
}

async function signInEveryone(base) {
  const people = {};
  for (const name of peopleNames) people[name] = await login(base, name);
  return people;
}

async function startPrivateConversation(bharat, base) {
  const page = bharat.page;
  await page.goto(origin + base + "/groups/new?conversation=1");
  await labelled(page, "Group name").fill("Bharat and Chitra private handoff");
  await labelled(page, "Find colleagues").fill("chitra");
  await page.getByRole("button", { name: /\+ Chitra Iyer/ }).click();
  await buttonNamed(page, "Create group with 1 colleague").click();
  await page.getByRole("heading", { level: 1, name: /Bharat and Chitra private handoff/ }).waitFor();
  check(page.url().endsWith("/chat"), base + " private conversation opens a two-person group chat");
  return page.url().match(/\/w\/([^/]+)/)[1];
}

async function checkLostUploadRecovery(bharat, base, form) {
  await loseNextResponse(bharat.page, "**/api/v1/uploads");
  await labelled(form, "Attach files").setInputFiles({
    name: "instrument-handoff.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await buttonNamed(form, "Check upload result").waitFor();
  await buttonNamed(form, "Check upload result").click();
  await buttonNamed(form, "Remove file: instrument-handoff.pdf").waitFor();
  check(true, base + " lost upload reply recovers original file through receipt");
}

async function checkLostSendRecovery(bharat, base, form, privateId) {
  const messageBox = labelled(form, "Message Bharat and Chitra private handoff");
  await messageBox.fill("Private instrument handoff — check reference drift first.");
  await loseNextResponse(bharat.page, "**/api/v1/workspaces/*/chat", { onlyPost: true });
  await buttonNamed(form, "Send").click();
  await buttonNamed(form, "Retry same message").waitFor();
  check(
    await labelled(form, "Attach files").isDisabled(),
    base + " unknown message freezes file selection and destination",
  );
  await buttonNamed(form, "Retry same message").click();
  await messageBox.waitFor();
  const messages = (await call(bharat, `/workspaces/${privateId}/chat`)).messages;
  check(
    messages.length === 1 && messages[0].attachments.length === 1,
    base + " lost send reply recovers one message and one binding",
  );
  return messages[0];
}

async function checkFileAccess(chitra, others, base, privateId, file) {
  await chitra.page.goto(origin + base + `/w/${privateId}/chat`);
  await chitra.page.getByRole("link", { name: "instrument-handoff.pdf", exact: true }).waitFor();
  const download = await chitra.ctx.request.get(origin + file.url);
  check(
    Buffer.from(await download.body()).equals(pdf),
    base + " colleague downloads authorized private handoff",
  );
  for (const actor of others) {
    const response = await actor.ctx.request.get(origin + file.url);
    check(response.status() === 404, base + " sibling division colleague/admin cannot retrieve private file");
  }
  await takeScreenshot(
    chitra,
    base,
    "-private-chat.png",
    "Private Bharat/Chitra handoff with an actual validated PDF attachment",
  );
}

async function checkThreadAttachment(bharat, base, message) {
  await bharat.page
    .getByRole("listitem")
    .filter({ has: bharat.page.getByText(message.body, { exact: true }) })
    .getByRole("button", { name: "Open thread", exact: true })
    .click();
  const thread = bharat.page.getByRole("region", { name: "Chat thread", exact: true });
  await labelled(thread, "Attach files").setInputFiles({
    name: "replicate-plan.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await buttonNamed(thread, "Remove file: replicate-plan.pdf").waitFor();
  await labelled(thread, "Thread reply").fill("Three replicates and a blank.");
  await buttonNamed(thread, "Send reply").click();
  await thread.getByRole("link", { name: "replicate-plan.pdf", exact: true }).waitFor();
  check(true, base + " reply shares a validated file inside original thread audience");
}

async function checkAttachmentLayouts(bharat, base) {
  for (const width of [1400, 390]) {
    await bharat.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(bharat.page);
    check(!violations.length, base + " attachments accessibility " + width + " " + violations);
    check(await hasNoSideScroll(bharat.page), base + " attachments overflow " + width);
  }
  await bharat.page.setViewportSize({ width: 1400, height: 1100 });
}

async function addIdea(user, groupId, index) {
  await call(user, `/workspaces/${groupId}/chat`, { body: ideas[index], client_id: crypto.randomUUID() });
  await call(user, `/workspaces/${groupId}/board/ops`, {
    epoch: 1,
    type: "add",
    op_id: crypto.randomUUID(),
    object_id: crypto.randomUUID(),
    payload: {
      kind: "sticky",
      data: { x: 30 + index * 190, y: 90, text: ideas[index], color: stickyColors[index] },
    },
  });
}

async function checkFivePersonGroup(bharat, people, base) {
  const everyone = Object.values(people);
  const group = await call(bharat, "/groups", {
    name: "Tejas C4 research discussion",
    description: "Synthetic collaboration across Thin Films, Corrosion and Surface Engineering Division.",
    member_ids: everyone.map((person) => person.session.user.id),
  });
  for (const [index, person] of everyone.entries()) await addIdea(person, group.id, index);
  for (const person of everyone) {
    await person.page.goto(origin + base + `/w/${group.id}/board`);
    await buttonNamed(person.page, "Fit").click();
  }
  await bharat.page.getByText(/5 here:/).waitFor();
  check(true, base + " five real sessions collaborate across sibling sections and parent division");
  await takeScreenshot(
    bharat,
    base,
    "-five-person-board.png",
    "Five-person cross-section research plan with shared native stickies",
  );
  const deepa = people.deepa;
  await deepa.page.goto(origin + base + `/w/${group.id}/chat`);
  await deepa.page.getByText(ideas[4], { exact: true }).waitFor();
  await takeScreenshot(
    deepa,
    base,
    "-group-chat.png",
    "Five researchers discuss controls and division review",
  );
}

async function checkUncertainGroupCreation(bharat, base) {
  const page = bharat.page;
  const createButton = buttonNamed(page, "Create group with 1 colleague");
  await page.goto(origin + base + "/groups/new?conversation=1");
  await labelled(page, "Group name").fill("Uncertain conversation review");
  await labelled(page, "Find colleagues").fill("asha");
  await page.getByRole("button", { name: /\+ Asha Rao/ }).click();
  await loseNextResponse(page, "**/api/v1/groups");
  await createButton.click();
  await page.getByText("Creation may have succeeded.", { exact: false }).waitFor();
  check(
    await createButton.isDisabled(),
    base + " uncertain private-group creation blocks blind duplicate submit",
  );
  await page.getByRole("link", { name: "Uncertain conversation review", exact: false }).waitFor();
  check(true, base + " group list reveals committed result for manual recovery");
}

async function checkRemovedColleague(bharat, chitra, base, privateId, file) {
  await chitra.page.goto(origin + base + `/w/${privateId}/chat`);
  await chitra.page.getByRole("link", { name: "instrument-handoff.pdf", exact: true }).waitFor();
  await call(bharat, `/groups/${privateId}/members/${chitra.session.user.id}`, undefined, "DELETE");
  await chitra.page
    .getByText(/This chat is no longer available\.|Workspace not available/)
    .first()
    .waitFor();
  const download = await chitra.ctx.request.get(origin + file.url);
  check(download.status() === 404, base + " removed colleague loses attachment and chat access");
}

function writeReport() {
  writeFileSync(
    outputDir + "/report.json",
    JSON.stringify({ checks: harness.checks(), shots: screenshots }, null, 2),
  );
  const gallery = screenshots
    .map((shot) => `<h2>${shot.label}</h2><img src="${shot.file}" alt="${shot.label}">`)
    .join("");
  writeFileSync(
    outputDir + "/index.html",
    '<!doctype html><meta charset="utf-8"><title>C4 synthetic collaboration</title>' +
      "<style>body{font:16px system-ui;max-width:1400px;margin:24px auto}img{max-width:100%}</style>" +
      "<h1>C4 synthetic collaboration</h1>" +
      gallery,
  );
}

try {
  for (const base of bases) {
    const admin = await login(base, "admin");
    const created = await activateMira(admin);
    const people = await signInEveryone(base);
    const { bharat, chitra } = people;
    const corrosion = (await call(chitra, "/workspaces")).workspaces.find(
      (workspace) => workspace.name === "Corrosion Section",
    );
    await call(
      admin,
      `/admin/workspaces/${corrosion.id}/memberships`,
      { user_id: created.user.id, role: "member" },
      "PUT",
    );
    const privateId = await startPrivateConversation(bharat, base);
    const form = bharat.page.getByRole("form", { name: "Send chat message", exact: true });
    await checkLostUploadRecovery(bharat, base, form);
    const message = await checkLostSendRecovery(bharat, base, form, privateId);
    const file = message.attachments[0];
    const outsiders = [people.asha, people.mira, people.deepa, admin];
    await checkFileAccess(chitra, outsiders, base, privateId, file);
    await checkThreadAttachment(bharat, base, message);
    await checkAttachmentLayouts(bharat, base);
    await checkFivePersonGroup(bharat, people, base);
    await checkUncertainGroupCreation(bharat, base);
    await checkRemovedColleague(bharat, chitra, base, privateId, file);
    check(
      Object.values(people).every((person) => !person.errors.length),
      base + " no browser exceptions",
    );
    await Promise.all([...Object.values(people).map((person) => person.ctx.close()), admin.ctx.close()]);
  }
  writeReport();
  console.log(`${harness.checks()} chat attachment browser checks passed`);
} finally {
  await harness.close();
}
