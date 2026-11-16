// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { WorkspaceProvider, useWorkspaces } from "./workspaces";
import type { Workspace } from "./types";

vi.mock("./api", () => ({ api: vi.fn(), errorMessage: () => "Request failed" }));
vi.mock("./realtime", () => ({ realtime: { subscribe: () => () => undefined } }));

type Response = { workspaces: Workspace[]; home_workspace_id: string | null };
function response(allowed: boolean): Response {
  return {
    home_workspace_id: "division",
    workspaces: [
      {
        id: "division",
        name: "Surface Engineering Division",
        kind: "org",
        parent_id: null,
        description: "",
        archived: false,
        posting_policy: "open",
        role: null,
        inherited: true,
        can_write: true,
        can_contribute: allowed,
        can_moderate: false,
        unread_chat: 0,
      },
    ],
  };
}
function Harness() {
  const { workspaces, reload, error } = useWorkspaces();
  return (
    <>
      <button onClick={() => void reload()}>Refresh access</button>
      <p>{workspaces[0]?.can_contribute ? "Can contribute" : "View only"}</p>
      {error && <p role="alert">{error}</p>}
    </>
  );
}

describe("workspace permission refresh", () => {
  it("ignores an older response after revocation and invalidates on unmount", async () => {
    const requests: Array<{ resolve: (value: Response) => void; reject: (reason: Error) => void }> = [];
    function requestAt(index: number) {
      const request = requests[index];
      if (!request) throw new Error(`Missing expected access request ${index}`);
      return request;
    }
    async function settle(index: number, value: Response | Error) {
      if (value instanceof Error) requestAt(index).reject(value);
      else requestAt(index).resolve(value);
      await Promise.resolve();
    }
    vi.mocked(api).mockImplementation(
      () => new Promise((resolve, reject) => requests.push({ resolve, reject })),
    );
    const mounted = render(
      <WorkspaceProvider>
        <Harness />
      </WorkspaceProvider>,
    );
    await waitFor(() => expect(requests).toHaveLength(1));
    await act(() => settle(0, response(true)));
    expect(screen.getByText("Can contribute")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Refresh access" }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh access" }));
    await act(() => settle(2, response(false)));
    expect(screen.getByText("View only")).toBeTruthy();
    await act(() => settle(1, response(true)));
    expect(screen.queryByText("Can contribute")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Refresh access" }));
    fireEvent.click(screen.getByRole("button", { name: "Refresh access" }));
    await act(() => settle(4, response(false)));
    await act(() => settle(3, new Error("Stale network failure")));
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Refresh access" }));
    mounted.unmount();
    await act(() => settle(5, response(true)));
  });
});
