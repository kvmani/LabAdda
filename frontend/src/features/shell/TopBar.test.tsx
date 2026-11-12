// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TopBar } from "./TopBar";

vi.mock("../../session", () => ({
  useSession: () => ({
    session: { user: { display_name: "Ben Okafor", is_admin: false } },
    signOut: vi.fn(),
  }),
}));
vi.mock("./WorkspaceSwitcher", () => ({ WorkspaceSwitcher: () => null }));

function show() {
  render(
    <MemoryRouter>
      <TopBar
        workspaces={[]}
        currentId={undefined}
        operations={false}
        unitAdmin={false}
        connection="online"
        unread={0}
        notificationsOpen={false}
        onToggleNotifications={() => undefined}
      />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Account menu for Ben Okafor" }));
}

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
});
afterEach(cleanup);

describe("account menu theme choice", () => {
  it("offers the three choices and marks the current one", () => {
    show();
    expect(screen.getByRole("menuitem", { name: "Theme: Follow the system (selected)" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Theme: Light" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Theme: Dark" })).toBeTruthy();
  });

  it("applies and remembers Dark, then returns to following the system", () => {
    show();
    fireEvent.click(screen.getByRole("menuitem", { name: "Theme: Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem("labadda.theme")).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "Account menu for Ben Okafor" }));
    expect(screen.getByRole("menuitem", { name: "Theme: Dark (selected)" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "Theme: Follow the system" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(window.localStorage.getItem("labadda.theme")).toBeNull();
  });
});
