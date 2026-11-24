// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { InsightsPage } from "./InsightsPage";
import { decisions, featureSeries, formatChange, parseSpan, parseWeeks, relative } from "./model";
import type { FeatureMomentum, Performance, Trends } from "./types";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const feature = (key: string, trend: FeatureMomentum["trend"], share: number | null): FeatureMomentum => ({
  key,
  label: `Label ${key}`,
  trend,
  advice: `Advice for ${key}`,
  weekly_recent: share === null ? null : 10,
  weekly_prior: 5,
  change: share === null ? null : 1,
  share,
  per_person: 2,
  sparkline: [null, 9, 4],
});

const trends: Trends = {
  weeks: 8,
  timezone: "UTC",
  generated_at: "2026-11-11T09:00:00+00:00",
  first_day: "2026-09-21",
  last_day: "2026-11-11",
  compare_weeks: 4,
  state: "measured",
  series: [{ key: "chat.messages", label: "Chat messages" }],
  points: [
    { start: "2026-10-26", partial: false, state: "suppressed", active_people: null, values: null },
    {
      start: "2026-11-02",
      partial: false,
      state: "measured",
      active_people: 7,
      values: { "chat.messages": 9 },
    },
    {
      start: "2026-11-09",
      partial: true,
      state: "measured",
      active_people: 6,
      values: { "chat.messages": 4 },
    },
  ],
  features: [
    feature("chat.messages", "growing", 0.8),
    feature("posts.created", "declining", 0.2),
    feature("tasks.created", "dormant", 0),
  ],
  people: {
    accounts: 20,
    weekly_recent: 6,
    weekly_prior: 5,
    change: 0.2,
    reach: 0.3,
    stickiness: 0.5,
    trend: "steady",
  },
};

const performance: Performance = {
  span: "7d",
  bucket: "hour",
  timezone: "UTC",
  generated_at: "2026-11-11T09:00:00+00:00",
  from: "2026-11-04T09:00:00+00:00",
  to: "2026-11-11T09:00:00+00:00",
  limits: { p95_ms: 1000, error_rate: 0.02 },
  state: "measured",
  current: {
    requests: 200,
    errors: 10,
    error_rate: 0.05,
    p50_ms: 40,
    p95_ms: 1200,
    status: "degraded",
    signin_ok: 30,
    signin_failed: 2,
    signin_failure_rate: 0.0625,
    peak_connections: 12,
  },
  previous: null,
  points: [],
  groups: [
    {
      key: "chat",
      label: "Chat",
      requests: 150,
      errors: 10,
      error_rate: 0.066,
      p50_ms: 50,
      p95_ms: 1500,
      previous_p95_ms: 1000,
      previous_requests: 90,
      status: "degraded",
    },
  ],
};

it("parses choices and describes change without inventing zero", () => {
  expect(parseWeeks("26")).toBe("26");
  expect(parseWeeks("5")).toBe("12");
  expect(parseSpan("90d")).toBe("90d");
  expect(parseSpan(null)).toBe("7d");
  expect(formatChange(null)).toBe("No earlier figure to compare");
  expect(formatChange(0.254)).toBe("Up 25 %");
  expect(formatChange(-0.5)).toBe("Down 50 %");
  expect(relative(5, 0)).toBeNull();
  expect(relative(15, 10)).toBeCloseTo(0.5);
});

it("groups features into focus, watch and drop, and charts only used features", () => {
  const grouped = decisions(trends.features);
  expect(grouped.focus.map((row) => row.key)).toEqual(["chat.messages"]);
  expect(grouped.watch.map((row) => row.key)).toEqual(["posts.created"]);
  expect(grouped.drop.map((row) => row.key)).toEqual(["tasks.created"]);
  const series = featureSeries(trends);
  expect(series.map((item) => item.label)).toEqual(["Label chat.messages", "Label posts.created"]);
  // The running week is left out of charts so it cannot look like a fall in use.
  expect(series[0]?.points.map((point) => point.value)).toEqual([null, 9]);
});

it("shows trends and their guidance", async () => {
  vi.mocked(api).mockResolvedValue(trends);
  render(
    <MemoryRouter initialEntries={["/admin/insights"]}>
      <InsightsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Focus here")).toBeTruthy();
  expect(screen.getByText("Candidates to simplify or retire")).toBeTruthy();
  expect(screen.getAllByText(/Advice for chat.messages/).length).toBeGreaterThan(0);
  expect(vi.mocked(api)).toHaveBeenCalledWith("/admin/insights/trends?weeks=12");
});

it("shows performance with the slowest area and an unmeasured comparison", async () => {
  vi.mocked(api).mockResolvedValue(performance);
  render(
    <MemoryRouter initialEntries={["/admin/insights?view=performance&span=7d"]}>
      <InsightsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("1,200 ms")).toBeTruthy();
  expect(screen.getByText("Chat")).toBeTruthy();
  expect(screen.getAllByText(/No earlier figure to compare/).length).toBeGreaterThan(0);
  expect(vi.mocked(api)).toHaveBeenCalledWith("/admin/insights/performance?span=7d");
});
