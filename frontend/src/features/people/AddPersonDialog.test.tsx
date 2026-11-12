// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import { AddPersonDialog } from "./AddPersonDialog";
import type { ChangePlan } from "./changeTypes";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const UNITS = [
  { id: "u1", name: "Catalysis Section", kind: "org", parent_id: null, archived: false },
  { id: "u2", name: "Closed Section", kind: "org", parent_id: null, archived: true },
];
const PLAN: ChangePlan = {
  kind: "add_person",
  revisions: {},
  steps: [
    {
      target_type: "identity",
      target_id: "new:gita",
      summary: "Create an invited account for Gita Sen (gita)",
      before: {},
      after: { username: "gita", status: "invited" },
    },
  ],
  warnings: [{ code: "similar_name", message: "Gita Sena (gsena) has a very similar name.", target_id: "p" }],
  blockers: [],
  affected_people: 1,
  digest: "a".repeat(64),
};

function fill() {
  fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: "Gita Sen" } });
  fireEvent.change(screen.getByLabelText(/Username/), { target: { value: "gita" } });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.change(screen.getByLabelText(/Home unit/), { target: { value: "u1" } });
  fireEvent.click(screen.getByRole("button", { name: "Review change" }));
}

it("reviews, applies with the digest and shows the code once on the slip", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(PLAN)
    .mockResolvedValueOnce({
      applied: true,
      kind: "add_person",
      person_id: "p2",
      revision: 1,
      digest: PLAN.digest,
      activation: { code: "slip-code-123456", expires_at: "2026-11-15T10:00:00Z" },
    });
  render(<AddPersonDialog units={UNITS} onClose={vi.fn()} onDenied={vi.fn()} onAdded={vi.fn()} />);
  expect(screen.queryByRole("option", { name: "Closed Section" })).toBeNull();
  fill();
  expect(await screen.findByText("Gita Sena (gsena) has a very similar name.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Reason for this change/), { target: { value: "New joiner" } });
  fireEvent.click(screen.getByRole("button", { name: "Add person" }));
  expect(await screen.findByText("slip-code-123456")).toBeTruthy();
  expect(vi.mocked(api).mock.calls[1]?.[1]).toMatchObject({
    body: { digest: PLAN.digest, revisions: {}, reason: "New joiner" },
  });
});

it("keeps the draft and shows a fresh plan after a conflict", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(PLAN)
    .mockRejectedValueOnce(new ApiError(409, "plan_stale", "stale"))
    .mockResolvedValueOnce({ ...PLAN, warnings: [] });
  render(<AddPersonDialog units={UNITS} onClose={vi.fn()} onDenied={vi.fn()} onAdded={vi.fn()} />);
  fill();
  await screen.findByText("Gita Sena (gsena) has a very similar name.");
  fireEvent.change(screen.getByLabelText(/Reason for this change/), { target: { value: "New joiner" } });
  fireEvent.click(screen.getByRole("button", { name: "Add person" }));
  expect(await screen.findByText(/Review the fresh plan before applying/)).toBeTruthy();
  await waitFor(() => expect(vi.mocked(api)).toHaveBeenCalledTimes(3));
  expect(screen.getByLabelText<HTMLTextAreaElement>(/Reason for this change/).value).toBe("New joiner");
});

it("reports lost administration access", async () => {
  vi.mocked(api).mockRejectedValueOnce(
    new ApiError(403, "admin_required", "Administrator access is required."),
  );
  const onDenied = vi.fn();
  render(<AddPersonDialog units={UNITS} onClose={vi.fn()} onDenied={onDenied} onAdded={vi.fn()} />);
  fill();
  await waitFor(() => expect(onDenied).toHaveBeenCalled());
});
