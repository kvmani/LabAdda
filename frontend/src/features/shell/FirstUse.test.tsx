// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionInfo } from "../../types";
import { FirstUse } from "./FirstUse";

const apiMock = vi.fn();
const patch = vi.fn();
let session: Partial<SessionInfo>;

vi.mock("../../api", () => ({
  api: (...args: unknown[]): unknown => apiMock(...args),
  errorMessage: () => "Could not save. Try again.",
}));
vi.mock("../../session", () => ({ useSession: () => ({ session, patch }) }));
vi.mock("../../workspaces", () => ({
  useWorkspaces: () => ({ loading: false, workspaces: [{ id: "home-1", name: "Thin Films Section" }] }),
}));

function show() {
  render(
    <MemoryRouter>
      <FirstUse />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  apiMock.mockReset().mockResolvedValue({ ok: true });
  patch.mockReset();
  session = {
    user: {
      id: "u",
      username: "ben",
      display_name: "Ben Okafor",
      is_active: true,
      is_admin: false,
      home_workspace_id: "home-1",
    },
    welcome_pending: true,
    whats_new_pending: false,
  };
});
afterEach(cleanup);

describe("FirstUse", () => {
  it("names the home unit, the three tabs and where help is", () => {
    show();
    expect(screen.getByRole("heading", { name: "Welcome to LabAdda, Ben Okafor" })).toBeTruthy();
    expect(screen.getByText(/Your home unit is Thin Films Section/)).toBeTruthy();
    for (const word of ["Noticeboard", "Whiteboard", "Chat"]) expect(screen.getByText(word)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Help" }).getAttribute("href")).toBe("/help");
  });

  it("saves the dismissal on the server before hiding", async () => {
    show();
    fireEvent.click(screen.getByRole("button", { name: "Got it, hide this" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith({ welcome_pending: false }));
    expect(apiMock).toHaveBeenCalledWith("/me/welcome/dismiss", { method: "POST" });
  });

  it("can be dismissed with the Escape key", async () => {
    show();
    fireEvent.keyDown(screen.getByRole("region", { name: /Welcome to LabAdda/ }), { key: "Escape" });
    await waitFor(() => expect(patch).toHaveBeenCalledWith({ welcome_pending: false }));
  });

  it("stays visible and says so when saving fails", async () => {
    apiMock.mockRejectedValue(new Error("down"));
    show();
    fireEvent.click(screen.getByRole("button", { name: "Got it, hide this" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Could not save. Try again.");
    expect(patch).not.toHaveBeenCalled();
  });

  it("shows nothing once dismissed and no release notes are pending", () => {
    session = { ...session, welcome_pending: false };
    show();
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("points to what is new once per release", async () => {
    session = { ...session, welcome_pending: false, whats_new_pending: true };
    show();
    expect(screen.getByRole("link", { name: "Read what is new" }).getAttribute("href")).toBe(
      "/help/whats-new",
    );
    fireEvent.click(screen.getByRole("button", { name: "Got it, hide this" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith({ whats_new_pending: false }));
    expect(apiMock).toHaveBeenCalledWith("/me/whats-new/seen", { method: "POST" });
  });
});
