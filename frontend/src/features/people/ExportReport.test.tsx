// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../../api";
import { ExportReport } from "./ExportReport";

vi.mock("../../api", async (original) => ({
  ...(await original<typeof import("../../api")>()),
  api: vi.fn(),
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it("ignores a denied download from an old filter scope", async () => {
  let reject: (error: Error) => void = () => undefined;
  vi.mocked(api).mockReturnValue(
    new Promise((_resolve, fail) => {
      reject = fail;
    }),
  );
  const onDenied = vi.fn();
  const { rerender } = render(<ExportReport key="old" url="/old" onDenied={onDenied} />);
  fireEvent.click(screen.getByRole("button", { name: "Export matching people" }));
  rerender(<ExportReport key="new" url="/new" onDenied={onDenied} />);
  await act(() => {
    reject(new ApiError(403, "forbidden", "Access changed."));
    return Promise.resolve();
  });
  expect(onDenied).not.toHaveBeenCalled();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("clears metadata on a denial in the active filter scope", async () => {
  vi.mocked(api).mockRejectedValue(new ApiError(403, "forbidden", "Access changed."));
  const onDenied = vi.fn();
  render(<ExportReport url="/current" onDenied={onDenied} />);
  await act(() => {
    fireEvent.click(screen.getByRole("button", { name: "Export matching people" }));
    return Promise.resolve();
  });
  expect(onDenied).toHaveBeenCalledOnce();
});

it("does not download an old report after filters change", async () => {
  let resolve: (value: Blob) => void = () => undefined;
  vi.mocked(api).mockReturnValue(
    new Promise((complete) => {
      resolve = complete;
    }),
  );
  const createObjectURL = vi.fn();
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
  const onDenied = vi.fn();
  const { rerender } = render(<ExportReport key="old" url="/old" onDenied={onDenied} />);
  fireEvent.click(screen.getByRole("button", { name: "Export matching people" }));
  rerender(<ExportReport key="new" url="/new" onDenied={onDenied} />);
  await act(() => {
    resolve(new Blob(["old report"], { type: "text/csv" }));
    return Promise.resolve();
  });
  expect(createObjectURL).not.toHaveBeenCalled();
  expect(screen.queryByRole("status")).toBeNull();
});
