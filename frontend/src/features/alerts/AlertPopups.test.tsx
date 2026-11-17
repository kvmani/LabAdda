// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AlertPopups } from "./AlertPopups";
const mocks = vi.hoisted(() => ({ api: vi.fn(), play: vi.fn(), enable: vi.fn(), close: vi.fn() }));
vi.mock("../../api", () => ({ api: mocks.api, errorMessage: () => "Could not save. Try again." }));
vi.mock("../../session", () => ({ useSession: () => ({ session: { user: { id: "asha" } } }) }));
vi.mock("../../workspaces", () => ({ useWorkspaces: () => ({ workspaces: [], reload: vi.fn() }) }));
vi.mock("./chime", () => ({
  AlertChime: class {
    play = mocks.play;
    enable = mocks.enable;
    close = mocks.close;
  },
}));
const item = {
  id: "meeting-1",
  title: "Project Tejas review",
  kind: "reminder",
  read: false,
  workspace: null,
  link: { view: "calendar" },
};
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});
function show() {
  return render(
    <MemoryRouter>
      <AlertPopups />
    </MemoryRouter>,
  );
}
it("dismisses without acknowledging and does not replay at the next poll", async () => {
  mocks.api.mockResolvedValue({ items: [item] });
  show();
  await screen.findByText(item.title);
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  await act(async () => {
    vi.advanceTimersByTime(10000);
    await Promise.resolve();
  });
  expect(screen.queryByText(item.title)).toBeNull();
  expect(mocks.api.mock.calls.every((call) => call[0] === "/notifications")).toBe(true);
});
it("keeps a failed acknowledgement visible; removes only after server confirmation", async () => {
  mocks.api.mockImplementation((path: string) =>
    path.endsWith("/open") ? Promise.reject(new Error()) : Promise.resolve({ items: [item] }),
  );
  show();
  await screen.findByText(item.title);
  fireEvent.click(screen.getByRole("button", { name: "Mark as read" }));
  await screen.findByRole("alert");
  expect(screen.getByText(item.title)).toBeTruthy();
  mocks.api.mockResolvedValue({ link: { view: "calendar" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark as read" }));
  await waitFor(() => expect(screen.queryByText(item.title)).toBeNull());
  expect(mocks.api).toHaveBeenCalledWith("/notifications/meeting-1/open", { method: "POST" });
});
it("requires a gesture to enable sound and allows muting", async () => {
  mocks.api.mockResolvedValue({ items: [] });
  show();
  expect(mocks.play).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Enable chime" }));
  await screen.findByRole("button", { name: "Mute chime" });
  expect(mocks.enable).toHaveBeenCalledOnce();
  expect(mocks.play).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("button", { name: "Mute chime" }));
  expect(screen.getByRole("button", { name: "Enable chime" })).toBeTruthy();
});
