import {
  axeViolations,
  bases,
  call,
  frameMark,
  hasNoSideScroll,
  holdFirstResponse,
  loseNextResponse,
  nextPaint,
  settleRequests,
  origin,
  startHarness,
  waitForSubscribed,
} from "./lib/harness.mjs";

const harness = await startHarness();
const { check, login } = harness;

const replyBox = (region) => region.getByLabel("Thread reply", { exact: true });
const buttonNamed = (scope, name) => scope.getByRole("button", { name, exact: true });
const textNamed = (scope, text) => scope.getByText(text, { exact: true });

async function openThread(user, base, workspaceId, rootBody) {
  await user.page.goto(origin + base + `/w/${workspaceId}/chat`);
  await user.page
    .getByRole("listitem")
    .filter({ has: textNamed(user.page, rootBody) })
    .getByRole("button", { name: "Open thread", exact: true })
    .click();
  return user.page.getByRole("region", { name: "Chat thread", exact: true });
}

function postChat(user, workspaceId, body) {
  return call(user, `/workspaces/${workspaceId}/chat`, { body, client_id: crypto.randomUUID() });
}

async function checkReplyDraftAndRecovery(ben, asha, base, workspaceId, root) {
  const region = await openThread(ben, base, workspaceId, root.body);
  const otherRegion = await openThread(asha, base, workspaceId, root.body);
  await replyBox(region).fill("Unsent uncertainty question");
  await replyBox(otherRegion).fill("Add a witness coupon");
  await buttonNamed(otherRegion, "Send reply").click();
  await textNamed(otherRegion, "Add a witness coupon").waitFor();
  await buttonNamed(region, "Refresh thread").click();
  await textNamed(region, "Add a witness coupon").waitFor();
  check(
    (await replyBox(region).inputValue()) === "Unsent uncertainty question",
    base + " thread refresh preserves reply draft",
  );
  await loseNextResponse(ben.page, "**/api/v1/workspaces/*/chat", { onlyPost: true });
  await buttonNamed(region, "Send reply").click();
  await buttonNamed(region, "Retry same message").waitFor();
  check(await replyBox(region).isDisabled(), base + " unknown reply freezes original intent");
  await buttonNamed(region, "Retry same message").click();
  await textNamed(region, "Unsent uncertainty question").waitFor();
  const replies = await call(ben, `/workspaces/${workspaceId}/chat/${root.id}/replies`);
  check(replies.messages.length === 2, base + " lost reply recovers one committed message");
}

async function checkThreadAccessibility(ben, base) {
  for (const width of [1400, 390]) {
    await ben.page.setViewportSize({ width, height: 1100 });
    const violations = await axeViolations(ben.page);
    check(!violations.length, base + " threads accessibility " + width + " " + violations);
    check(await hasNoSideScroll(ben.page), base + " threads overflow " + width);
  }
}

async function checkDelayedOlderPage(ben, asha, base, workspaceId) {
  for (let index = 0; index < 52; index++) {
    await postChat(asha, workspaceId, "History sample " + index);
  }
  const page = ben.page;
  await buttonNamed(page, "Refresh chat").click();
  await textNamed(page, "History sample 51").waitFor();
  const olderPage = await holdFirstResponse(page, "**/api/v1/workspaces/*/chat?before=*");
  await buttonNamed(page, "Load earlier messages").click();
  await olderPage.captured;
  await buttonNamed(page, "Return to latest messages").click();
  await textNamed(page, "History sample 51").waitFor();
  // Listen only now: the held response is delivered to the page when it is released.
  const delivered = page.waitForResponse((response) => response.url().includes("/chat?before="));
  olderPage.release();
  await (await delivered).finished();
  await nextPaint(page);
  const latestShown = await textNamed(page, "History sample 51").isVisible();
  const returnButtons = await buttonNamed(page, "Return to latest messages").count();
  check(latestShown && returnButtons === 0, base + " delayed older page cannot override latest view");
}

async function checkLiveUpdateKeepsEarlierView(ben, asha, base, workspaceId) {
  const page = ben.page;
  await buttonNamed(page, "Load earlier messages").click();
  await buttonNamed(page, "Return to latest messages").waitFor();
  const background = page.waitForResponse(
    async (response) =>
      response.url().includes("/chat?after=") &&
      (await response.json()).messages.some((message) => message.body === "Newest history decision"),
  );
  await postChat(asha, workspaceId, "Newest history decision");
  await (await background).finished();
  const stillEarlier = await buttonNamed(page, "Return to latest messages").isVisible();
  const noticeShown = await buttonNamed(page, "Load more new messages").isVisible();
  check(stillEarlier && noticeShown, base + " live updates retain earlier view and new-message notice");
  await buttonNamed(page, "Return to latest messages").click();
  await textNamed(page, "Newest history decision").waitFor();
  check(true, base + " explicit return restores latest messages");
}

async function checkReconnectCatchUp(ben, asha, base, workspaceId) {
  const page = ben.page;
  // Hold a pre-disconnect HTTP snapshot; reconnect must queue another catch-up.
  const snapshot = await holdFirstResponse(page, "**/api/v1/workspaces/*/chat?*");
  await buttonNamed(page, "Refresh chat").click();
  await snapshot.captured;
  const reconnected = page.waitForEvent("websocket");
  const beforeClose = frameMark(ben);
  await page.evaluate(() => window.__sockets.at(-1).close());
  await postChat(asha, workspaceId, "Offline control decision");
  await reconnected;
  // The new socket's confirmation must arrive while the old snapshot is still held, so the
  // catch-up it triggers is the one that has to queue behind that snapshot.
  await waitForSubscribed(ben, workspaceId, beforeClose);
  snapshot.release();
  await textNamed(page, "Offline control decision").waitFor();
  check(true, base + " reconnect queued behind held snapshot catches offline writes");
}

async function checkRevocation(ben, admin, base, workspaceId) {
  // A workspace-list reload that overlaps the membership removal can fail on the server.
  await settleRequests(ben);
  // The workspace page replaces the chat once its own reload answers "not found"; holding that
  // answer keeps the chat's notice on screen so the check does not depend on which lands first.
  const heldDetail = await holdFirstResponse(ben.page, `**/api/v1/workspaces/${workspaceId}`);
  const removal = `/admin/workspaces/${workspaceId}/memberships/${ben.session.user.id}`;
  await call(admin, removal, undefined, "DELETE");
  await textNamed(ben.page, "This chat is no longer available.").waitFor();
  const composers = await replyBox(ben.page).count();
  const rootShown = await textNamed(ben.page, "Research control plan").count();
  check(composers === 0 && rootShown === 0, base + " revocation clears thread stream and composer");
  heldDetail.release();
  await settleRequests(ben);
}

try {
  for (const base of bases) {
    const ben = await login(base, "ben", { trackSockets: true });
    const asha = await login(base, "asha");
    const admin = await login(base, "admin");
    const workspaces = (await call(ben, "/workspaces")).workspaces;
    const workspaceId = workspaces.find((workspace) => workspace.name === "Thin Films Section").id;
    const root = await postChat(asha, workspaceId, "Research control plan");
    await checkReplyDraftAndRecovery(ben, asha, base, workspaceId, root);
    await checkThreadAccessibility(ben, base);
    await checkDelayedOlderPage(ben, asha, base, workspaceId);
    await checkLiveUpdateKeepsEarlierView(ben, asha, base, workspaceId);
    await checkReconnectCatchUp(ben, asha, base, workspaceId);
    await checkRevocation(ben, admin, base, workspaceId);
    check(!ben.errors.length && !asha.errors.length, base + " no browser exceptions");
    await Promise.all([ben.ctx.close(), asha.ctx.close(), admin.ctx.close()]);
  }
  console.log(`${harness.checks()} chat thread browser checks passed`);
} finally {
  await harness.close();
}
