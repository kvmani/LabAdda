// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import type { ChangePlan } from "../people/changeTypes";
import { OrgPage } from "./OrgPage";
import type { OrgTree } from "./types";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const unit = (id: string, name: string, parent: string | null, code: string, extra = {}) => ({
  id,
  name,
  code,
  parent_id: parent,
  archived: false,
  head: null,
  acting_head: null,
  stewards: [],
  people: 1,
  members: 1,
  level: null,
  ...extra,
});
const TREE: OrgTree = {
  units: [
    unit("root", "National Materials Research Laboratory", null, "NMRL", {
      head: { id: "h", name: "Deepa Nair" },
    }),
    unit("div", "Surface Engineering Division", "root", "SED"),
    unit("tf", "Thin Films Section", "div", "TFS"),
    unit("old", "Retired Lab", "div", "RL", { archived: true }),
  ],
  spaces: [
    {
      id: "p",
      kind: "project",
      name: "Project Tejas",
      archived: false,
      stewards: [{ id: "d", name: "Deepa Nair" }],
      members: 2,
    },
  ],
};
const PLAN: ChangePlan = {
  kind: "unit_move",
  revisions: {},
  steps: [
    {
      target_type: "workspace",
      target_id: "tf",
      summary: "Move Thin Films Section with its sub-units under National Materials Research Laboratory",
      before: { parent: "Surface Engineering Division" },
      after: { parent: "National Materials Research Laboratory" },
    },
  ],
  warnings: [
    {
      code: "access_lost",
      message: "1 person will no longer be able to read Surface Engineering Division.",
      target_id: "div",
      count: 1,
    },
  ],
  blockers: [],
  affected_people: 1,
  digest: "b".repeat(64),
};

function serve(extra: Record<string, unknown> = {}) {
  vi.mocked(api).mockImplementation((path: string) => {
    if (path in extra) return Promise.resolve(extra[path]);
    if (path === "/admin/org/tree") return Promise.resolve(TREE);
    if (path === "/admin/org/unit-admins") return Promise.resolve({ items: [] });
    if (path.startsWith("/admin/people")) return Promise.resolve({ people: [], next_cursor: null });
    return Promise.reject(new Error(`unexpected request ${path}`));
  });
}
const open = () =>
  render(
    <MemoryRouter>
      <OrgPage />
    </MemoryRouter>,
  );

it("draws the chart with codes, heads and counts, hides closed units, and lists projects beside it", async () => {
  serve();
  open();
  const tree = await screen.findByRole("tree", { name: "Organisation units" });
  const items = within(tree).getAllByRole("treeitem");
  expect(items.map((item) => item.getAttribute("aria-label"))).toEqual([
    "NMRL, National Materials Research Laboratory. Head Deepa Nair. 1 person",
    "SED, Surface Engineering Division. No head. 1 person",
    "TFS, Thin Films Section. No head. 1 person",
  ]);
  expect(screen.getByText("Project Tejas")).toBeTruthy();
  expect(screen.getByText(/Steward: Deepa Nair · 2 members/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText("Show closed units"));
  expect(within(tree).getAllByRole("treeitem")).toHaveLength(4);
});

it("moves between units with the keyboard and selects with Enter", async () => {
  serve();
  open();
  const root = (await screen.findAllByRole("treeitem"))[0] as HTMLElement;
  root.focus();
  fireEvent.keyDown(root, { key: "ArrowDown" });
  const division = screen.getByRole("treeitem", { name: /Surface Engineering Division/ });
  expect(division.getAttribute("tabindex")).toBe("0"); // jsdom cannot focus SVG; the roving stop moved
  fireEvent.keyDown(division, { key: "Enter" });
  expect(await screen.findByRole("heading", { name: "Surface Engineering Division" })).toBeTruthy();
  fireEvent.keyDown(division, { key: " " });
  expect(screen.queryByRole("treeitem", { name: /Thin Films/ })).toBeNull();
  fireEvent.keyDown(division, { key: "ArrowDown" });
  expect(screen.getByRole("treeitem", { name: /Thin Films/ })).toBeTruthy();
});

it("offers Move to… from the panel, shows the server's review and applies the reviewed plan", async () => {
  serve({
    "/admin/changes/preview": PLAN,
    "/admin/changes/apply": { applied: true, kind: "unit_move", unit_id: "tf", digest: PLAN.digest },
  });
  open();
  fireEvent.click(await screen.findByRole("treeitem", { name: /Thin Films Section/ }));
  expect(await screen.findByRole("button", { name: "Move to…" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Merge into…" })).not.toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Move to…" }));
  fireEvent.change(await screen.findByLabelText(/Move under/), { target: { value: "root" } });
  fireEvent.click(screen.getByRole("button", { name: "Review change" }));
  expect(await screen.findByText(/1 person will no longer be able to read/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Reason for this change/), { target: { value: "Reorganised" } });
  fireEvent.click(screen.getByRole("button", { name: "Move Thin Films Section" }));
  expect(await screen.findByText("Thin Films Section has been moved.")).toBeTruthy();
  const body = vi.mocked(api).mock.calls.find(([path]) => path === "/admin/changes/apply")?.[1];
  expect(body).toMatchObject({ body: { digest: PLAN.digest, reason: "Reorganised" } });
});

it("keeps the top unit from being moved, merged, split or closed", async () => {
  serve();
  open();
  fireEvent.click(await screen.findByRole("treeitem", { name: /National Materials Research Laboratory/ }));
  await screen.findByRole("button", { name: "Add sub-unit" });
  for (const name of ["Move to…", "Merge into…", "Split off a new unit…", "Close unit"])
    expect(screen.queryByRole("button", { name })).toBeNull();
});

it("finds a unit by code and reveals it", async () => {
  serve();
  open();
  fireEvent.change(await screen.findByLabelText("Find a unit or person"), { target: { value: "tfs" } });
  fireEvent.click(await screen.findByRole("button", { name: "Show Thin Films Section" }, { timeout: 2000 }));
  expect(await screen.findByRole("heading", { name: "Thin Films Section" })).toBeTruthy();
});

it("shows a plain error when the chart cannot load, and reports lost access", async () => {
  vi.mocked(api).mockRejectedValue(
    new ApiError(503, "people_unavailable", "Staff information is unavailable."),
  );
  open();
  expect(await screen.findByText(/Staff information is unavailable/)).toBeTruthy();
  cleanup();
  vi.mocked(api).mockRejectedValue(new ApiError(403, "admin_required", "Administrator access is required."));
  open();
  await waitFor(() => expect(screen.getByText("Your administration access changed")).toBeTruthy());
});
