// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../../api";
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
    trend: [1, 2, 3],
    updated_at: null,
  }) satisfies OverviewTile;

function mockOverview(): Overview {
  return {
    generated_at: "2026-11-16T18:00:00+00:00",
    timezone: "UTC",
    period: { first_day: "2026-11-09", last_day: "2026-11-16" },
    overall: "healthy",
    attention: [],
    tiles: [
      tile("active_today", "people", "measured", 12),
      tile("storage_used", "bytes", "measured", 2048),
      tile("open_events", "events", "measured", 1),
    ],
    charts: {
      activity: { state: "measured", points: [] },
      response_time: { state: "unknown", unit: "ms", points: [] },
    },
    cockpit: {
      generated_at: "2026-11-16T18:00:00+00:00",
      timezone: "UTC",
      kpis: {
        total_accounts: 50,
        active_accounts: 48,
        adoption_rate: 96,
        total_workspaces: 19,
        workspaces_by_kind: { org: 10, project: 5, group: 4 },
        total_collaboration_items: 85,
        total_storage_bytes: 52428800,
        total_storage_formatted: "50.0 MB",
        open_events_count: 1,
        events_by_severity: { warning: 1, critical: 0 },
      },
      popular_workspaces: [
        {
          id: "ws-tejas",
          name: "Project Tejas",
          kind: "project",
          description: "Aeronautics trial",
          members_count: 8,
          has_steward: true,
          total_items: 34,
          posts_count: 12,
          chats_count: 18,
          tasks_count: 4,
        },
        {
          id: "ws-corrosion",
          name: "Corrosion Section",
          kind: "org",
          description: "Surface testing",
          members_count: 6,
          has_steward: false,
          total_items: 21,
          posts_count: 5,
          chats_count: 10,
          tasks_count: 6,
        },
      ],
      bottlenecks: {
        storage: {
          top_workspaces: [
            { id: "ws-tejas", name: "Project Tejas", kind: "project", bytes: 31457280, formatted: "30.0 MB" },
            {
              id: "ws-corrosion",
              name: "Corrosion Section",
              kind: "org",
              bytes: 10485760,
              formatted: "10.0 MB",
            },
          ],
          headroom_status: "Storage usage is nominal across all teams.",
        },
        governance: {
          unstaffed_units_count: 1,
          unstaffed_units: ["Corrosion Section"],
          unstaffed_projects_count: 0,
          unstaffed_projects: [],
        },
        performance: {
          p95_latency_ms: 120,
          latency_status: "Fast (< 300 ms)",
        },
        reliability: {
          open_events: [
            {
              id: "ev-1",
              code: "STALE_BACKUP",
              component: "backup",
              severity: "warning",
              summary: "No database backup created in last 24 hours",
              first_at: "2026-11-16T12:00:00Z",
              last_at: "2026-11-16T17:00:00Z",
              recommendation: "Run a manual backup verification from Admin > Backups.",
            },
          ],
          critical_count: 0,
          warning_count: 1,
        },
      },
      usage_patterns: {
        feature_distribution: [
          {
            feature: "Chat Messages",
            count: 45,
            percentage: 53,
            icon: "💬",
            role: "Real-time lab discussion",
          },
          {
            feature: "Noticeboard Posts",
            count: 25,
            percentage: 29,
            icon: "📢",
            role: "Official lab announcements",
          },
          { feature: "Tasks & Checklists", count: 15, percentage: 18, icon: "📋", role: "Action tracking" },
        ],
        peak_summary: "Peak intranet activity: 10:00 AM - 12:30 PM & 3:00 PM - 5:30 PM",
      },
    },
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

async function mount() {
  vi.mocked(api).mockResolvedValue(mockOverview());
  render(
    <MemoryRouter>
      <OverviewPage />
    </MemoryRouter>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

it("renders 360-degree cockpit KPIs on load", async () => {
  await mount();

  // Adoption KPI
  expect(screen.getByText("Staff Adoption")).toBeTruthy();
  expect(screen.getByText("96% Active")).toBeTruthy();
  expect(screen.getByText("/ 50")).toBeTruthy();

  // Collaboration Velocity KPI
  expect(screen.getByText("Collaboration Items")).toBeTruthy();
  expect(screen.getByText("85")).toBeTruthy();

  // Storage Footprint KPI
  expect(screen.getByText("Content Storage")).toBeTruthy();
  expect(screen.getByText("50.0 MB")).toBeTruthy();

  // System Events KPI
  expect(screen.getByText("System Events")).toBeTruthy();
  expect(screen.getByText("Warnings to review")).toBeTruthy();
});

it("switches tabs between Overview, Trends, Bottlenecks, and Diagnostics", async () => {
  await mount();

  // Default tab is 360 Overview
  expect(screen.getByRole("tab", { name: /360° Overview/i }).getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText("Most Active Collaboration Workspaces")).toBeTruthy();
  expect(screen.getByText("Project Tejas")).toBeTruthy();

  // Switch to Usage Trends & Popularity tab
  const trendsTab = screen.getByRole("tab", { name: /Usage Trends/i });
  fireEvent.click(trendsTab);
  expect(trendsTab.getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText("Feature Adoption & Usage Distribution")).toBeTruthy();
  expect(screen.getByText("Chat Messages")).toBeTruthy();
  expect(screen.getByText("53% of activity")).toBeTruthy();
  expect(screen.getByText(/10:00 AM - 12:30 PM/)).toBeTruthy();

  // Switch to Bottlenecks & SLA tab
  const bottlenecksTab = screen.getByRole("tab", { name: /Bottlenecks/i });
  fireEvent.click(bottlenecksTab);
  expect(bottlenecksTab.getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText("Storage Consumption by Workspace")).toBeTruthy();
  expect(screen.getByText("1 Units Need Stewards")).toBeTruthy();
  expect(screen.getByText("Fast (< 300 ms)")).toBeTruthy();
  expect(screen.getByText("120 ms")).toBeTruthy();

  // Switch to Action & Diagnostics tab
  const diagnosticsTab = screen.getByRole("tab", { name: /Action & Diagnostics/i });
  fireEvent.click(diagnosticsTab);
  expect(diagnosticsTab.getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText("System Diagnostic & Action Center")).toBeTruthy();
  expect(screen.getByText("No database backup created in last 24 hours")).toBeTruthy();
  expect(screen.getByText(/Run a manual backup verification/)).toBeTruthy();
});
