// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import { BackupsPage, formatAge } from "./BackupsPage";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("states ages in whole units", () => {
  expect(formatAge(30)).toBe("Just now");
  expect(formatAge(3 * 3600)).toBe("3 hours ago");
  expect(formatAge(5 * 86400)).toBe("5 days ago");
});

it("shows an unknown backup as unknown, with guidance and no details", async () => {
  vi.mocked(api).mockResolvedValue({
    status: "unknown",
    headline: "No backup has been recorded.",
    guidance: "Ask the person who looks after the server.",
    checked_at: "2026-11-11T10:00:00Z",
    healthy_within_hours: 26,
    stale_after_hours: 50,
    last_backup: null,
  });
  render(
    <MemoryRouter>
      <BackupsPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Unknown")).toBeTruthy();
  expect(screen.getByText("Ask the person who looks after the server.")).toBeTruthy();
  expect(screen.queryByText("Verification")).toBeNull();
});
