// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BroadcastStrip } from "./BroadcastStrip";
import type { SiteMessage } from "./types";

const messages: SiteMessage[] = [
  { id: 1, message: "Server restart at six", level: "warning" },
  { id: 2, message: "Library <b>closed</b> Monday", level: "info" },
];

function prefersReducedMotion(reduced: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => ({
      matches: reduced,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("renders nothing when there are no messages", () => {
  prefersReducedMotion(false);
  const { container } = render(<BroadcastStrip messages={[]} />);
  expect(container.firstChild).toBeNull();
});

it("scrolls the messages, shows markup as typed and speaks them once in a polite region", () => {
  prefersReducedMotion(false);
  render(<BroadcastStrip messages={messages} />);
  const strip = screen.getByTestId("broadcast-strip");
  expect(strip.className).toContain("broadcast-strip--warning");
  expect(strip.querySelector("b")).toBeNull();
  expect(screen.getAllByText("Library <b>closed</b> Monday").length).toBeGreaterThan(0);
  const live = screen.getByRole("status");
  expect(live.getAttribute("aria-live")).toBe("polite");
  expect(live.textContent).toBe("Warning: Server restart at six Notice: Library <b>closed</b> Monday");
  expect(strip.querySelector(".broadcast-strip__window")?.getAttribute("aria-hidden")).toBe("true");
});

it("pauses and plays with a visible button", () => {
  prefersReducedMotion(false);
  render(<BroadcastStrip messages={messages} />);
  const strip = screen.getByTestId("broadcast-strip");
  fireEvent.click(screen.getByRole("button", { name: "Pause announcements" }));
  expect(strip.className).toContain("broadcast-strip--paused");
  const play = screen.getByRole("button", { name: "Play announcements" });
  expect(play.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(play);
  expect(strip.className).not.toContain("broadcast-strip--paused");
});

it("lists the messages still, with no pause button, under reduced motion", () => {
  prefersReducedMotion(true);
  render(<BroadcastStrip messages={messages} />);
  expect(screen.getByTestId("broadcast-strip").className).toContain("broadcast-strip--still");
  expect(screen.queryByRole("button")).toBeNull();
});
