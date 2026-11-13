// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { Broadcast } from "../broadcast/types";
import { BroadcastPage } from "./BroadcastPage";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const row = (id: number, message: string, changes: Partial<Broadcast> = {}): Broadcast => ({
  id,
  message,
  level: "warning",
  starts_at: null,
  ends_at: null,
  active: true,
  position: id,
  status: "showing",
  revision: 1,
  ...changes,
});

function show(broadcasts: Broadcast[]) {
  vi.mocked(api).mockImplementation((path: string) =>
    Promise.resolve(path === "/admin/broadcasts" ? { broadcasts, max_length: 300 } : {}),
  );
  render(
    <MemoryRouter>
      <BroadcastPage />
    </MemoryRouter>,
  );
}

it("explains an empty list", async () => {
  show([]);
  expect(await screen.findByText("No broadcast messages")).toBeTruthy();
});

it("lists messages with plain status words", async () => {
  show([row(1, "Pilot notice"), row(2, "Later", { status: "scheduled", active: true })]);
  expect(await screen.findByText("Pilot notice")).toBeTruthy();
  expect(screen.getByText("Showing now")).toBeTruthy();
  expect(screen.getByText("Waiting for start time")).toBeTruthy();
});

it("adds a message", async () => {
  show([]);
  await screen.findByText("No broadcast messages");
  fireEvent.click(screen.getAllByRole("button", { name: "Add broadcast message" })[0]!);
  fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: "Back at six." } });
  fireEvent.click(screen.getByRole("button", { name: "Add message" }));
  await waitFor(() => expect(vi.mocked(api).mock.calls.some(([, o]) => o?.method === "POST")).toBe(true));
  const post = vi.mocked(api).mock.calls.find(([, options]) => options?.method === "POST");
  expect(post?.[0]).toBe("/admin/broadcasts");
  expect(post?.[1]).toMatchObject({ body: { message: "Back at six.", level: "info", active: true } });
});

it("turns a message off with the revision it last read", async () => {
  show([row(7, "Pilot notice", { revision: 4 })]);
  fireEvent.click(await screen.findByRole("button", { name: "Turn off" }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/admin/broadcasts/7", {
      method: "PATCH",
      body: { active: false, expected_revision: 4 },
    }),
  );
});

it("asks before deleting, and only deletes after the confirmation", async () => {
  show([row(7, "Pilot notice")]);
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  const dialog = await screen.findByRole("dialog");
  expect(api).not.toHaveBeenCalledWith("/admin/broadcasts/7", expect.anything());
  fireEvent.click(within(dialog).getByRole("button", { name: "Delete broadcast message" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/admin/broadcasts/7", { method: "DELETE" }));
});
