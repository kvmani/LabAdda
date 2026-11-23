// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, cleanup, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import type { RealtimeEvent } from "../../realtime";
import { AlertPopups } from "./AlertPopups";
const mocks = vi.hoisted(() => ({ api: vi.fn(), play: vi.fn(), enable: vi.fn(), close: vi.fn() }));
vi.mock("../../api", () => ({ api: mocks.api, errorMessage: () => "Could not save. Try again." }));
vi.mock("../../session", () => ({ useSession: () => ({ session: { user: { id: "asha" } } }) }));
const listeners = vi.hoisted(() => new Map<string, (event: RealtimeEvent) => void>());
vi.mock("../../realtime", () => ({
  realtime: {
    subscribe(id: string, listener: (event: RealtimeEvent) => void) {
      listeners.set(id, listener);
      return () => listeners.delete(id);
    },
  },
}));
vi.mock("../../workspaces", () => ({
  useWorkspaces: () => ({ workspaces: [{ id: "section", name: "Thin Films" }], reload: vi.fn() }),
}));
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
  vi.useFakeTimers();
  await act(async () => {
    show();
    await Promise.resolve();
  });
  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  await act(() => vi.advanceTimersByTimeAsync(10000));
  expect(mocks.api).toHaveBeenCalledTimes(2);
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

it("restores an unread reminder with its current title when the connection recovers", async () => {
  mocks.api
    .mockResolvedValueOnce({ items: [item] })
    .mockRejectedValueOnce(new Error("Network unavailable"))
    .mockResolvedValueOnce({ items: [{ ...item, title: "Project Tejas design review" }] });
  vi.useFakeTimers();
  await act(async () => {
    show();
    await Promise.resolve();
  });
  expect(screen.getByText(item.title)).toBeTruthy();
  await act(() => vi.advanceTimersByTimeAsync(10000));
  expect(screen.queryByText(item.title)).toBeNull();
  await act(() => vi.advanceTimersByTimeAsync(10000));
  expect(screen.getByText("Project Tejas design review")).toBeTruthy();
});

const chat = (seq: number): RealtimeEvent => ({
  type: "chat.message",
  message: {
    workspace_id: "section",
    id: String(seq),
    seq,
    body: `Thin Films update ${seq}`,
    author: { id: "bharat", username: "bharat", display_name: "Bharat", is_active: true },
    attachments: [],
    parent_id: null,
    client_id: String(seq),
    created_at: "2026-11-23T09:00:00Z",
  },
});

it("continues receiving chat after access is rechecked and suppresses a revoked workspace", async () => {
  mocks.api.mockResolvedValue({ items: [] });
  await act(async () => {
    show();
    await Promise.resolve();
  });
  const send = listeners.get("section")!;
  act(() => {
    send({ type: "access_changed" });
    send(chat(1));
  });
  expect(screen.getByText("Thin Films update 1")).toBeTruthy();
  act(() => {
    send({ type: "revoked", workspace_id: "section" });
    send(chat(2));
  });
  expect(screen.queryByText("Thin Films update 1")).toBeNull();
  expect(screen.queryByText("Thin Films update 2")).toBeNull();
});

it("keeps an unread mention visible after acknowledging a later chat message", async () => {
  const mention = {
    ...item,
    kind: "mention",
    title: "@asha please check",
    link: { view: "chat", workspace_id: "section", seq: 1 },
  };
  mocks.api.mockResolvedValue({ items: [mention] });
  show();
  await screen.findByText(mention.title);
  act(() => listeners.get("section")!(chat(2)));
  fireEvent.click(
    within(screen.getByRole("region", { name: "New chat message" })).getByRole("button", {
      name: "Mark as read",
    }),
  );
  await waitFor(() => expect(screen.queryByText("Thin Films update 2")).toBeNull());
  expect(screen.getByText(mention.title)).toBeTruthy();
});
