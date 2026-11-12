// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { ActivityPage } from "./ActivityPage";
import { comparison, featureSeries, figureText, heatValues, parsePeriod, tileValue } from "./model";
import type { Summary, SummaryCharts, Tile, Units } from "./types";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const range = { first_day: "2026-11-05", last_day: "2026-11-11" };
const common = {
  period: "7d" as const,
  timezone: "UTC",
  generated_at: "2026-11-11T09:00:00+00:00",
  current: range,
  previous: range,
};
const tile = (key: Tile["key"], value: number | null, previous: number | null): Tile => ({
  key,
  label: `Label ${key}`,
  unit: "people",
  state: value === null ? "unknown" : "measured",
  value,
  previous_state: previous === null ? "unknown" : "measured",
  previous,
});
const charts: SummaryCharts = {
  active_per_day: [
    { day: "2026-11-10", state: "suppressed", value: null },
    { day: "2026-11-11", state: "measured", value: 6 },
  ],
  features: {
    bucket: "day",
    series: [{ key: "posts.created", label: "Posts" }],
    points: [
      { start: "2026-11-10", state: "suppressed", values: null },
      { start: "2026-11-11", state: "measured", values: { "posts.created": 2, "replies.created": 1 } },
    ],
  },
  items_by_kind: [{ key: "project", label: "Projects", state: "measured", value: 4 }],
  weekday_hour: {
    state: "measured",
    from: "2026-11-05T00:00:00+00:00",
    cells: [{ weekday: 3, hour: 9, value: 7 }],
    suppressed_weekdays: [7],
  },
  storage: [],
  upload_sizes: [{ key: "under_100kb", label: "Under 100 KB", state: "measured", value: 1 }],
};
const units: Units = {
  ...common,
  minimum_group: 5,
  rounded_to: 5,
  state: "measured",
  units: [
    {
      id: "u1",
      name: "Thin Films Section",
      parent_id: null,
      archived: false,
      active_people: { state: "suppressed" },
      items_created: { state: "suppressed" },
      previous_active_people: null,
    },
  ],
  no_home_unit: null,
  chart: [],
};

function mount(summary: Summary) {
  vi.mocked(api).mockImplementation((path: string) =>
    Promise.resolve(path.includes("/units") ? units : summary),
  );
  render(
    <MemoryRouter initialEntries={["/admin/activity?period=7d"]}>
      <ActivityPage />
    </MemoryRouter>,
  );
}

it("reads the period from the address and falls back to 30 days", () => {
  expect(parsePeriod("90d")).toBe("90d");
  expect(parsePeriod("14d")).toBe("30d");
  expect(parsePeriod(null)).toBe("30d");
});

it("describes comparisons in words and unknown as not measured", () => {
  expect(comparison(tile("active_day", 5, 3))).toBe("Up 2 from 3 in the previous period.");
  expect(comparison(tile("active_day", 5, null))).toBe("No figures for the previous period.");
  expect(comparison(tile("active_day", null, null))).toBe("No figures were collected in this period.");
  expect(figureText({ state: "suppressed" })).toBe("Fewer than 5");
  expect(figureText({ state: "shown", value: 10 })).toBe("10");
  expect(figureText(null)).toBe("Not applicable");
  const hidden: Tile = {
    ...tile("active_day", null, null),
    state: "suppressed",
    previous_state: "suppressed",
  };
  expect(tileValue(hidden)).toBe("Fewer than 5");
  expect(comparison(hidden)).toBe("Fewer than 5 people were active, so the number is hidden.");
  expect(comparison({ ...tile("active_day", 7, null), previous_state: "suppressed" })).toBe(
    "Fewer than 5 in the previous period.",
  );
});

it("keeps unmeasured buckets as gaps and fills the heat grid", () => {
  const noticeboard = featureSeries(charts)[0];
  expect(noticeboard?.points.map((point) => point.value)).toEqual([null, 3]);
  expect(heatValues(charts)[2]?.[9]).toBe(7);
  expect(heatValues(charts)[0]?.[0]).toBeNull();
});

it("says an empty installation is not measured instead of showing zeros", async () => {
  mount({ ...common, state: "unknown", tiles: [], charts: null });
  expect(await screen.findByText("Not measured yet")).toBeTruthy();
  expect(screen.queryByText("0")).toBeNull();
});

it("shows suppressed units as fewer than 5 and leaves them out of the chart", async () => {
  mount({ ...common, state: "measured", tiles: [tile("active_day", 3, null)], charts });
  expect(await screen.findByText("Label active_day")).toBeTruthy();
  expect(screen.getAllByText("Fewer than 5").length).toBeGreaterThan(0);
  expect(screen.getByText(/No unit has enough active people/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Export figures" })).toBeTruthy();
  expect(screen.getByText(/Days with fewer than 5 active people are left out/)).toBeTruthy();
  expect(screen.getByText(/Weekdays with fewer than 5 active people are left empty/)).toBeTruthy();
});
