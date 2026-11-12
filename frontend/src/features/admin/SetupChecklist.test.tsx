// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import { SetupChecklist, type SetupChecklistData } from "./SetupChecklist";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));

const data: SetupChecklistData = {
  checked_at: "2026-11-12T10:00:00Z",
  done: 1,
  total: 3,
  items: [
    {
      key: "second_admin",
      label: "A second administrator",
      state: "done",
      detail: "2 active administrators.",
      screen: "/admin/people",
      help: "admin/add-a-person",
    },
    {
      key: "backups",
      label: "Backups reporting healthy",
      state: "unknown",
      detail: "No backup has been recorded.",
      screen: "/admin/backups",
      help: "admin/backups-page",
    },
    {
      key: "units",
      label: "Organisation units created",
      state: "not_done",
      detail: "0 units below the top of the organisation.",
      screen: "/admin/org",
      help: "admin/create-move-merge-close-units",
    },
  ],
};

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

async function mount() {
  render(
    <MemoryRouter>
      <SetupChecklist />
    </MemoryRouter>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

it("shows each item with its state word and links to its screen and help page", async () => {
  vi.mocked(api).mockResolvedValue(data);
  await mount();
  expect(screen.getByText("1 of 3 done")).toBeTruthy();
  expect(screen.getByText("Done")).toBeTruthy();
  expect(screen.getByText("Unknown")).toBeTruthy();
  expect(screen.getByText("Not done")).toBeTruthy();
  const open = screen.getByLabelText("Open the page for: Backups reporting healthy");
  expect(open.getAttribute("href")).toBe("/admin/backups");
  const help = screen.getByLabelText("Read the help for: A second administrator");
  expect(help.getAttribute("href")).toBe("/help/admin/add-a-person");
  expect(screen.queryByRole("checkbox")).toBeNull();
});

it("says so when the checklist cannot be read", async () => {
  vi.mocked(api).mockRejectedValue(new Error("down"));
  await mount();
  expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  expect(screen.queryByText("Done")).toBeNull();
});

it("clears the list when access is taken away", async () => {
  vi.mocked(api).mockRejectedValue(new ApiError(403, "admin_required", "Administrator access is required."));
  await mount();
  expect(screen.getByText("Your administration access changed")).toBeTruthy();
  expect(screen.queryByText("A second administrator")).toBeNull();
});
