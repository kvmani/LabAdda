// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { HealthPage } from "./HealthPage";
import type { HealthItem, HealthReport } from "./types";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));

const item = (key: string, label: string, status: HealthItem["status"], value: HealthItem["value"]) => ({
  key,
  label,
  status,
  value,
  unit: "ms",
  detail: `${label} detail.`,
  checked_at: "2026-11-11T12:00:00+00:00",
  age_seconds: 8,
  help: `troubleshooting/health-${key}`,
  chart: null,
});
const report = (items: HealthItem[], overall: HealthReport["overall"]): HealthReport => ({
  overall,
  generated_at: "2026-11-11T12:00:08+00:00",
  interval_seconds: 15,
  items,
});

function visibility(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
}

beforeEach(() => {
  vi.useFakeTimers();
  visibility("visible");
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

async function mount(data: HealthReport) {
  vi.mocked(api).mockResolvedValue(data);
  render(
    <MemoryRouter>
      <HealthPage />
    </MemoryRouter>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

it("never shows unknown or missing figures as healthy or zero", async () => {
  await mount(
    report(
      [item("backups", "Backups", "unknown", null), item("database", "Database", "healthy", 3)],
      "unknown",
    ),
  );
  expect(
    screen.getByText("Some checks have no figures yet, so the system is not confirmed healthy."),
  ).toBeTruthy();
  expect(screen.getByText("Not measured")).toBeTruthy();
  expect(screen.getAllByText("Unknown")).toHaveLength(2);
  // Only items that are not healthy offer the guide.
  expect(screen.getAllByRole("link", { name: /^What to do/ })).toHaveLength(1);
  expect(screen.getByRole("link", { name: "What to do: Backups" }).getAttribute("href")).toBe(
    "/help/troubleshooting/health-backups",
  );
});

it("says how old each check is and marks it stale once it is too old", async () => {
  await mount(report([item("database", "Database", "healthy", 3)], "healthy"));
  expect(screen.getByText("Checked 8 s ago")).toBeTruthy();
  await act(async () => {
    vi.mocked(api).mockRejectedValue(new Error("offline"));
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(screen.getAllByText("Stale")).toHaveLength(2);
  expect(screen.getByRole("alert").textContent).toContain("could not be refreshed");
});

it("polls every 15 seconds but not while the tab is hidden", async () => {
  await mount(report([item("database", "Database", "healthy", 3)], "healthy"));
  const calls = () => vi.mocked(api).mock.calls.filter(([path]) => path === "/admin/health").length;
  expect(calls()).toBe(1);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(15_000);
  });
  expect(calls()).toBe(2);
  visibility("hidden");
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60_000);
  });
  expect(calls()).toBe(2);
  visibility("visible");
  await act(async () => {
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);
  });
  expect(calls()).toBe(3);
});
