// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { ExcelImportDialog } from "./ExcelImportDialog";
import type { StaffReport } from "./staffImport";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const GOOD: StaffReport = {
  rows: [
    {
      line: 2,
      display_name: "Ananya Iyer",
      username: "ananya.iyer",
      place: "Materials Group > Surface Engineering Division",
      role: "admin",
      access: "code",
      errors: [],
      warnings: ["Will become an administrator."],
    },
  ],
  total: 1,
  errors: 0,
  units_to_create: [{ name: "Materials Group", level: "group", under: [] }],
  administrators: ["Ananya Iyer"],
  plan: {
    kind: "bulk",
    revisions: {},
    steps: [
      {
        target_type: "workspace",
        target_id: "new:unit",
        summary: "Create the group Materials Group (MG) under NR",
        before: {},
        after: {},
      },
    ],
    warnings: [],
    blockers: [],
    affected_people: 1,
    digest: "a".repeat(64),
  },
};

function pick(name: string) {
  const input = screen.getByLabelText("Staff sheet file");
  fireEvent.change(input, { target: { files: [new File(["x"], name)] } });
}

it("refuses other file types without calling the server", async () => {
  render(<ExcelImportDialog onClose={() => undefined} onDenied={() => undefined} onDone={() => undefined} />);
  pick("people.pdf");
  expect(await screen.findByText(/Choose an Excel workbook/)).toBeTruthy();
  expect(api).not.toHaveBeenCalled();
});

it("shows the administrator warning, then applies with the digest and a reason", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce(GOOD)
    .mockResolvedValueOnce({
      applied: true,
      kind: "bulk",
      digest: GOOD.plan?.digest,
      count: 2,
      added: [
        {
          person_id: "p",
          username: "ananya.iyer",
          display_name: "Ananya Iyer",
          activation: { code: "ABCD-1234", expires_at: "2027-01-01T00:00:00Z" },
        },
      ],
    });
  render(<ExcelImportDialog onClose={() => undefined} onDenied={() => undefined} onDone={() => undefined} />);
  pick("staff.xlsx");
  expect(await screen.findByText(/will become an administrator/i)).toBeTruthy();
  expect(screen.getByText(/Create the group Materials Group/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Reason for this change/), {
    target: { value: "Pilot onboarding" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Add 1 person" }));
  await waitFor(() => expect(screen.getByText(/Activation codes are shown only once/)).toBeTruthy());
  const call = vi.mocked(api).mock.calls[1];
  expect(call?.[0]).toBe("/admin/changes/import/staff/apply");
  expect(call?.[1]?.headers).toMatchObject({
    "X-Import-Digest": "a".repeat(64),
    "X-Import-Reason": "Pilot%20onboarding",
  });
});

it("lists the problems and offers no apply button when any row is wrong", async () => {
  vi.mocked(api).mockResolvedValueOnce({
    ...GOOD,
    errors: 1,
    plan: null,
    rows: [{ ...GOOD.rows[0]!, errors: ["Emp No is required but this row leaves it blank."] }],
  });
  render(<ExcelImportDialog onClose={() => undefined} onDenied={() => undefined} onDone={() => undefined} />);
  pick("staff.xlsx");
  expect(await screen.findByText(/Emp No is required/)).toBeTruthy();
  expect(screen.getByText(/Nothing was saved/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /^Add / })).toBeNull();
});
