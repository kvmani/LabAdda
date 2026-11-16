// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { api } from "../../api";
import { useWorkspaces } from "../../workspaces";
import type { Workspace } from "../../types";
import { PublishSummary } from "./PublishSummary";
vi.mock("../../api", () => ({
  api: vi.fn(),
  newId: () => "summary-test",
  errorMessage: () => "Request failed",
}));
vi.mock("../../workspaces", () => ({ useWorkspaces: vi.fn() }));
const source: Workspace = {
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
  can_contribute: false,
  can_moderate: false,
  unread_chat: 0,
};
const section: Workspace = { ...source, id: "section", name: "Thin Films Section", can_contribute: true };
function workspaces(items: Workspace[]) {
  vi.mocked(useWorkspaces).mockReturnValue({
    workspaces: items,
    homeId: null,
    loading: false,
    error: null,
    reload: vi.fn(),
  });
}
it("defaults to an eligible destination and confirms its audience before posting", async () => {
  workspaces([source, section]);
  vi.mocked(api).mockResolvedValue({});
  const close = vi.fn();
  const view = render(<PublishSummary source={source} text="Reviewed chat summary" onClose={close} />);
  expect(screen.getByLabelText<HTMLSelectElement>("Destination").value).toBe("section");
  const post = screen.getByRole<HTMLButtonElement>("button", { name: "Post to Thin Films Section" });
  expect(post.disabled).toBe(true);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(post);
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith("/workspaces/section/posts", {
      body: { body: "Reviewed chat summary", client_id: "summary-test" },
    }),
  );
  expect(close).toHaveBeenCalledOnce();
  view.unmount();
});
it("blocks direct form submission when there is no eligible destination", () => {
  vi.mocked(api).mockClear();
  workspaces([source]);
  const view = render(<PublishSummary source={source} text="Retain this draft" onClose={vi.fn()} />);
  expect(screen.getByRole<HTMLButtonElement>("button", { name: "Post summary" }).disabled).toBe(true);
  fireEvent.submit(screen.getByRole("form", { name: "Publish chat summary" }));
  expect(api).not.toHaveBeenCalled();
  expect(screen.getByLabelText<HTMLTextAreaElement>("Summary").value).toBe("Retain this draft");
  view.unmount();
});
