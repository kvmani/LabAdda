// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { AttentionList } from "./AttentionList";
import { ChangeDialog } from "./ChangeDialog";
import { ScheduledChanges } from "./ScheduledChanges";
import type { ChangePlan } from "./changeTypes";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const ITEM = {
  id: "s1",
  kind: "transfer",
  effective_on: "2030-01-07",
  state: "needs_review",
  note: "Something this change depends on was changed after it was scheduled.",
  reason: "Moves with the new term",
  subject_id: "p1",
  steps: ["Move Ben Okafor to Catalysis Section"],
  created_by: "Site Administrator",
  created_at: "2026-11-01T10:00:00Z",
};
const PLAN: ChangePlan = {
  kind: "suspend",
  revisions: { p1: 2 },
  steps: [],
  warnings: [],
  blockers: [],
  affected_people: 1,
  digest: "b".repeat(64),
};

it("lists a change needing review with its reason and cancels it with a reason", async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [ITEM] });
  render(<ScheduledChanges onDenied={vi.fn()} />);
  expect(await screen.findByText(/Needs review/)).toBeTruthy();
  expect(screen.getByText(/changed after it was scheduled/)).toBeTruthy();
  expect(screen.getByText("Move Ben Okafor to Catalysis Section")).toBeTruthy();
  vi.mocked(api).mockResolvedValueOnce({ cancelled: true }).mockResolvedValueOnce({ items: [] });
  fireEvent.click(screen.getByRole("button", { name: "Dismiss this change" }));
  fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Plans changed" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel this change" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/admin/changes/scheduled/s1", {
      method: "DELETE",
      params: { reason: "Plans changed" },
    }),
  );
  expect(await screen.findByText("No changes are scheduled.")).toBeTruthy();
});

it("shows nothing on a profile with no scheduled changes", async () => {
  vi.mocked(api).mockResolvedValueOnce({ items: [] });
  const { container } = render(<ScheduledChanges personId="p1" onDenied={vi.fn()} />);
  await waitFor(() => expect(api).toHaveBeenCalled());
  expect(container.textContent).toBe("");
});

it("lists attention items with a link to the fix", async () => {
  vi.mocked(api).mockResolvedValueOnce({
    items: [
      {
        id: "people:no-home-unit",
        severity: "warning",
        title: "1 person has no home unit",
        detail: "Ben Okafor. Transfer them.",
        route: "/admin/people",
      },
    ],
  });
  render(
    <MemoryRouter>
      <AttentionList onDenied={vi.fn()} />
    </MemoryRouter>,
  );
  expect(await screen.findByText("1 person has no home unit")).toBeTruthy();
  expect(screen.getByRole("link", { name: /fixes this/ }).getAttribute("href")).toBe("/admin/people");
});

function openDialog(kind: "suspend" | "reinstate") {
  const request = { kind, person_id: "p1" } as const;
  render(
    <ChangeDialog
      title="Suspend"
      formId="f"
      request={request}
      confirmLabel="Apply"
      busyLabel="Applying…"
      done={() => <p>Applied.</p>}
      onClose={vi.fn()}
      onDenied={vi.fn()}
      onDone={vi.fn()}
    />,
  );
}

it("schedules a reviewed change for a later day and says nothing changes until then", async () => {
  vi.mocked(api).mockResolvedValue(PLAN);
  openDialog("suspend");
  await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText(/When should this happen/), { target: { value: "later" } });
  fireEvent.change(screen.getByLabelText(/Day it takes effect/), { target: { value: "2030-01-07" } });
  await waitFor(() =>
    expect(api).toHaveBeenLastCalledWith("/admin/changes/preview", {
      body: { request: { kind: "suspend", person_id: "p1" }, effective_on: "2030-01-07" },
    }),
  );
  await screen.findByRole("button", { name: "Schedule change" });
  fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "End of contract" } });
  vi.mocked(api).mockResolvedValueOnce({ scheduled: true, id: "s1", effective_on: "2030-01-07" });
  fireEvent.click(screen.getByRole("button", { name: "Schedule change" }));
  expect(await screen.findByText(/Nothing changes until then/)).toBeTruthy();
  const calls = vi.mocked(api).mock.calls;
  const body = calls[calls.length - 1]?.[1]?.body as Record<string, unknown>;
  expect(body.effective_on).toBe("2030-01-07");
  expect(body.digest).toBe(PLAN.digest);
});

it("does not offer a later day for a change that issues an activation code", async () => {
  vi.mocked(api).mockResolvedValue({ ...PLAN, kind: "reinstate" });
  openDialog("reinstate");
  await waitFor(() => expect(api).toHaveBeenCalled());
  expect(screen.queryByLabelText(/When should this happen/)).toBeNull();
});
