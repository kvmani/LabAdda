// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { tileValue } from "./model";
import { OverviewPage } from "./OverviewPage";
import type { Overview, OverviewTile } from "./types";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));

const tile = (key: string, unit: OverviewTile["unit"], state: OverviewTile["state"], value: number | null) =>
  ({
    key,
    label: `Tile ${key}`,
    unit,
    link: `/admin/${key}`,
    state,
    value,
    trend: key === "last_backup" ? null : [1, null, 2, 3, 4, 5, 6],
    updated_at: null,
  }) satisfies OverviewTile;

const days = [
  "2026-11-06",
  "2026-11-07",
  "2026-11-08",
  "2026-11-09",
  "2026-11-10",
  "2026-11-11",
  "2026-11-12",
];
function overview(changes: Partial<Overview> = {}): Overview {
  return {
    generated_at: "2026-11-12T10:00:00+00:00",
    timezone: "UTC",
    period: { first_day: days[0] ?? "", last_day: days[6] ?? "" },
    overall: "healthy",
    attention: [],
    tiles: [
      tile("active_today", "people", "measured", 12),
      tile("signed_in_now", "people", "suppressed", null),
      tile("connected_now", "connections", "unknown", null),
      tile("storage_used", "bytes", "measured", 2048),
      tile("last_backup", "seconds", "healthy", 3600),
      tile("open_events", "events", "measured", 0),
    ],
    charts: {
      activity: { state: "measured", points: days.map((day) => ({ day, state: "measured", value: 9 })) },
      response_time: { state: "unknown", unit: "ms", points: [] },
    },
    ...changes,
  };
}

beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

async function mount(data: Overview) {
  vi.mocked(api).mockResolvedValue(data);
  render(
    <MemoryRouter>
      <OverviewPage />
    </MemoryRouter>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

it("says plainly that nothing needs attention", async () => {
  await mount(overview());
  expect(screen.getByText("Nothing needs attention")).toBeTruthy();
  expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "Tile storage_used" }).getAttribute("href")).toBe(
    "/admin/storage_used",
  );
});

it("never shows a hidden or missing figure as zero", async () => {
  await mount(overview());
  expect(screen.getByText("Fewer than 5")).toBeTruthy();
  expect(screen.getAllByText("Not measured").length).toBeGreaterThan(0);
  expect(screen.queryByText("0 people")).toBeNull();
  expect(tileValue(tile("x", "people", "unknown", null))).toBe("Not measured");
});

it("lists attention entries in the order sent, each linking to its page", async () => {
  await mount(
    overview({
      overall: "unavailable",
      attention: [
        {
          id: "health:backups",
          kind: "health",
          severity: "error",
          status: "unavailable",
          title: "Backups",
          detail: "No recent backup exists.",
          route: "/admin/backups",
          help: "troubleshooting/health-backups",
          at: null,
        },
        {
          id: "people:units-without-steward",
          kind: "people",
          severity: "warning",
          status: null,
          title: "1 unit has no steward or Head",
          detail: "Catalysis Section.",
          route: "/admin/org",
          help: null,
          at: null,
        },
      ],
    }),
  );
  const items = screen.getAllByRole("listitem").filter((node) => node.className === "overview-entry");
  expect(items).toHaveLength(2);
  expect(items[0]?.textContent).toContain("Backups");
  expect(screen.getByRole("link", { name: "Open Backups" }).getAttribute("href")).toBe("/admin/backups");
  expect(screen.getByRole("link", { name: "Open 1 unit has no steward or Head" }).getAttribute("href")).toBe(
    "/admin/org",
  );
  expect(screen.getByText("2 things need attention.")).toBeTruthy();
  expect(screen.queryByText("Nothing needs attention")).toBeNull();
});

it("marks old figures stale when refreshing keeps failing", async () => {
  await mount(overview());
  vi.mocked(api).mockRejectedValue(new Error("down"));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(75_000);
  });
  expect(screen.getByText("These figures are out of date.")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("could not be refreshed");
});
