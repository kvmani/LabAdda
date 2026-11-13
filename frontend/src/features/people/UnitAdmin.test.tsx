// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { ConsoleAccess } from "../admin/console";
import { UnitAdministrators } from "../org/UnitAdministrators";
import { PeoplePage } from "./PeoplePage";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const BRANCH = {
  units: [
    {
      id: "tf",
      name: "Thin Films Section",
      code: "TFS",
      parent_id: null,
      archived: false,
      head: null,
      acting_head: null,
      stewards: [],
      people: 2,
      members: 2,
    },
  ],
  spaces: [],
};
const DIRECTORY = {
  people: [
    {
      id: "p1",
      username: "bharat",
      display_name: "Bharat Kulkarni",
      employee_no: null,
      designation: null,
      status: "active",
      revision: 1,
      is_admin: false,
      sign_in_enabled: true,
      home_unit: { id: "tf", name: "Thin Films Section" },
      last_seen_on: null,
      positions: [],
    },
  ],
  next_cursor: null,
};

function renderPeople(access: ConsoleAccess) {
  return render(
    <MemoryRouter initialEntries={["/admin/people"]}>
      <Routes>
        <Route element={<Outlet context={access} />}>
          <Route path="/admin/people" element={<PeoplePage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

it("gives a unit administrator only their branch and none of the site-wide tools", async () => {
  vi.mocked(api).mockImplementation((path: string) => {
    if (path === "/admin/org/tree") return Promise.resolve(BRANCH);
    if (path.startsWith("/admin/people")) return Promise.resolve(DIRECTORY);
    return Promise.reject(new Error(`unexpected request ${path}`));
  });
  renderPeople({ sections: ["people", "org"], read_only: false, unit_admin: true });
  expect(await screen.findByText("Bharat Kulkarni")).toBeTruthy();
  const asked = vi.mocked(api).mock.calls.map((call) => String(call[0]));
  expect(asked.some((path) => path.startsWith("/admin/workspaces"))).toBe(false);
  expect(asked).not.toContain("/admin/org/attention");
  expect(screen.queryByRole("button", { name: "Import staff list" })).toBeNull();
  expect(screen.queryByText("Basic account tools")).toBeNull();
  expect(screen.queryByText("Needs attention")).toBeNull();
  await waitFor(() =>
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Add person" }).disabled).toBe(false),
  );
});

it("lists appointments and withdraws one through the reviewed change", async () => {
  vi.mocked(api).mockImplementation((path: string) => {
    if (path === "/admin/org/unit-admins")
      return Promise.resolve({
        items: [
          {
            id: "g1",
            person: { id: "p1", name: "Deepa Nair" },
            unit: { id: "sed", name: "Surface Engineering Division", archived: false },
            granted_by: "Site Administrator",
            granted_at: "2026-11-01T10:00:00Z",
          },
        ],
      });
    return Promise.resolve({
      steps: [],
      warnings: [],
      blockers: [],
      revisions: { p1: 1 },
      digest: "a".repeat(64),
    });
  });
  render(<UnitAdministrators onDenied={vi.fn()} onChanged={vi.fn()} />);
  expect(await screen.findByText(/Deepa Nair administers Surface Engineering Division/)).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: "Withdraw Deepa Nair from Surface Engineering Division" }),
  );
  await waitFor(() => {
    const preview = vi.mocked(api).mock.calls.find((call) => call[0] === "/admin/changes/preview");
    expect(preview?.[1]?.body).toMatchObject({
      request: { kind: "unit_admin_revoke", person_id: "p1", unit_id: "sed" },
    });
  });
});
