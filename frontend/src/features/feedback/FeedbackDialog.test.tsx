// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FeedbackDialog } from "./FeedbackDialog";
import { admitFiles } from "./model";

const api = vi.fn<(path: string, options?: { form?: FormData }) => Promise<unknown>>();
vi.mock("../../api", () => ({
  api: (path: string, options?: { form?: FormData }) => api(path, options),
  errorMessage: (failure: unknown) => (failure instanceof Error ? failure.message : "Failed"),
}));

const FACTS = {
  username: "bharat",
  time: "2026-11-13T09:00:00+00:00",
  software_version: "0.0.1-beta",
  commit: "abc1234",
  max_message: 5000,
  max_files: 5,
  max_file_bytes: 1000,
  max_total_bytes: 1500,
  email_copy: false,
};

function show() {
  render(
    <MemoryRouter initialEntries={["/w/thin-films/board"]}>
      <FeedbackDialog open onClose={() => undefined} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  api.mockReset();
  api.mockImplementation((path: string) =>
    path === "/feedback/form" ? Promise.resolve(FACTS) : Promise.resolve({ id: "1" }),
  );
});
afterEach(cleanup);

describe("feedback dialog", () => {
  it("tells people administrators will read it and shows what is sent", async () => {
    show();
    expect(screen.getByText(/Administrators will read this message and its attachments/)).toBeTruthy();
    expect(await screen.findByText("bharat")).toBeTruthy();
    expect(screen.getByText("abc1234")).toBeTruthy();
    expect(screen.getByText("/w/thin-films/board")).toBeTruthy();
  });

  it("keeps the draft when sending fails, then confirms only after the server answers", async () => {
    show();
    await screen.findByText("bharat");
    fireEvent.change(screen.getByLabelText(/Your message/), { target: { value: "Sensor graph is blank" } });
    api.mockImplementationOnce(() => Promise.reject(new Error("Cannot reach LabAdda.")));
    fireEvent.click(screen.getByRole("button", { name: "Send to the administrators" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Your message is kept");
    expect(screen.getByLabelText<HTMLTextAreaElement>(/Your message/).value).toBe("Sensor graph is blank");
    fireEvent.click(screen.getByRole("button", { name: "Send to the administrators" }));
    await waitFor(() => expect(screen.getByText(/Sent to the administrators/)).toBeTruthy());
    const sends = api.mock.calls.filter((call) => call[0] === "/feedback");
    const ids = sends.map((call) => call[1]?.form?.get("client_id"));
    expect(ids[0]).toBe(ids[1]);
  });

  it("refuses an empty message without calling the server", async () => {
    show();
    await screen.findByText("bharat");
    fireEvent.click(screen.getByRole("button", { name: "Send to the administrators" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(api.mock.calls.filter((call) => call[0] === "/feedback")).toHaveLength(0);
  });
});

describe("choosing files", () => {
  const limits = { maxFiles: 2, maxFileBytes: 100, maxTotalBytes: 150 };
  const file = (name: string, size: number, type = "image/png") =>
    new File([new Uint8Array(size)], name, { type });
  it("explains each file that does not fit", () => {
    const result = admitFiles(
      [],
      [
        file("a.png", 90),
        file("big.png", 200),
        file("c.exe", 5, "application/x-msdownload"),
        file("d.png", 90),
      ],
      limits,
    );
    expect(result.files.map((f) => f.name)).toEqual(["a.png"]);
    expect(result.problems).toHaveLength(3);
    expect(result.problems[0]).toContain("big.png is too large");
    expect(result.problems[2]).toContain("together");
  });
  it("stops at the file count", () => {
    const result = admitFiles([file("a.png", 5), file("b.png", 5)], [file("c.png", 5)], limits);
    expect(result.files).toHaveLength(2);
    expect(result.problems[0]).toContain("up to 2 files");
  });
});
