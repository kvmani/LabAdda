// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { ImportDialog } from "./ImportDialog";
import type { ChangePlan, ImportReport } from "./changeTypes";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const REPORT: ImportReport = {
  rows: [
    {
      line: 2,
      group: "add",
      username: "gita",
      display_name: "Gita Sen",
      summary: ["Create an invited account for Gita Sen (gita)"],
      errors: [],
      warnings: [],
      requests: [
        {
          kind: "add_person",
          username: "gita",
          display_name: "Gita Sen",
          fields: {},
          home_unit_id: "u1",
          role: "member",
        },
      ],
    },
    {
      line: 3,
      group: "errors",
      username: "ghost",
      display_name: "Ghost",
      summary: [],
      errors: ["No open unit has the code ZZZ."],
      warnings: [],
      requests: [],
    },
  ],
  counts: { add: 1, change: 0, transfer: 0, errors: 1, unchanged: 0 },
  absent: [{ username: "asha", display_name: "Asha Rao" }],
  absent_total: 1,
  digest: "d".repeat(64),
};
const PLAN: ChangePlan = {
  kind: "bulk",
  revisions: {},
  steps: [],
  warnings: [],
  blockers: [],
  affected_people: 1,
  digest: "a".repeat(64),
};

function upload(file: File) {
  const input = screen.getByLabelText<HTMLInputElement>("Staff list CSV file");
  fireEvent.change(input, { target: { files: [file] } });
}

it("rejects a non-CSV file before sending anything", async () => {
  render(<ImportDialog onClose={vi.fn()} onDenied={vi.fn()} onDone={vi.fn()} />);
  upload(new File(["x"], "people.xlsx"));
  expect((await screen.findByRole("alert")).textContent).toMatch(/\.csv/);
  expect(api).not.toHaveBeenCalled();
});

it("shows grouped rows, keeps error rows unselectable, and applies only the selection", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(REPORT)
    .mockResolvedValueOnce(PLAN)
    .mockResolvedValueOnce({
      applied: true,
      kind: "bulk",
      digest: PLAN.digest,
      count: 1,
      added: [
        {
          person_id: "p",
          username: "gita",
          display_name: "Gita Sen",
          activation: { code: "slip-code-123456", expires_at: "2026-11-15T10:00:00Z" },
        },
      ],
    });
  render(<ImportDialog onClose={vi.fn()} onDenied={vi.fn()} onDone={vi.fn()} />);
  upload(new File(["username\n"], "people.csv"));
  const report = await screen.findByRole("region", { name: "Import report" });
  expect(within(report).getByText("No open unit has the code ZZZ.")).toBeTruthy();
  expect(within(report).queryByRole("checkbox", { name: /Line 3/ })).toBeNull();
  expect(vi.mocked(api).mock.calls[0]?.[1]?.raw?.type).toBe("text/csv");
  expect(within(report).getByText(/1 people are not in the file/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Review 1 selected row" }));
  await screen.findByRole("button", { name: "Apply 1 change" });
  expect(vi.mocked(api).mock.calls[1]).toEqual([
    "/admin/changes/bulk/preview",
    { body: { requests: REPORT.rows[0]?.requests } },
  ]);
  fireEvent.change(await screen.findByLabelText(/Reason for this change/), {
    target: { value: "Autumn joiners" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Apply 1 change" }));
  await waitFor(() => expect(screen.getByText("slip-code-123456")).toBeTruthy());
  expect(vi.mocked(api).mock.calls[2]?.[0]).toBe("/admin/changes/bulk/apply");
});

it("select all per group clears and restores the rows", async () => {
  vi.mocked(api).mockResolvedValueOnce(REPORT);
  render(<ImportDialog onClose={vi.fn()} onDenied={vi.fn()} onDone={vi.fn()} />);
  upload(new File(["username\n"], "people.csv"));
  const all = await screen.findByRole("checkbox", { name: /Select all in/ });
  fireEvent.click(all);
  expect(screen.getByRole<HTMLButtonElement>("button", { name: "Review 0 selected rows" }).disabled).toBe(
    true,
  );
  fireEvent.click(all);
  expect(screen.getByRole("button", { name: "Review 1 selected row" })).toBeTruthy();
});
