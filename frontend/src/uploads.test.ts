import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { UploadQueue } from "./uploads";
vi.mock("./api", () => ({
  api: vi.fn(),
  newId: () => `upload-${++sequence}`,
  ApiError: class extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
    ) {
      super(message);
    }
  },
}));
let sequence = 0;
const request = vi.mocked(api);
const file = () => new File(["%PDF-fixture"], "fixture.pdf", { type: "application/pdf" });
const asset = {
  id: "asset-01",
  display_name: "fixture.pdf",
  status: "provisional",
  media_type: "application/pdf",
  size: 12,
  url: "/file",
  preview_url: null,
};
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const offline = () => new ApiError(0, "offline", "offline");
beforeEach(() => {
  request.mockReset();
});
afterEach(() => vi.useRealTimers());

describe("upload recovery", () => {
  it("retains the exact file and request key on explicit transport retry", async () => {
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete),
      original = file();
    request.mockRejectedValueOnce(offline()).mockResolvedValueOnce(asset);
    queue.add([original], 1);
    await settle();
    const key = queue.snapshot()[0]!.key;
    await queue.send(key);
    expect(request.mock.calls.map((c) => c[1]?.uploadKey)).toEqual([key, key]);
    expect(request.mock.calls[0]![1]?.form?.get("file")).toBe(original);
    expect(request.mock.calls[1]![1]?.form?.get("file")).toBe(original);
    expect(complete).toHaveBeenCalledTimes(1);
    expect(complete).toHaveBeenCalledWith(asset);
    expect(queue.snapshot()).toEqual([]);
  });
  it("recovers a committed result by reading status without another POST", async () => {
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete);
    request.mockRejectedValueOnce(offline()).mockResolvedValueOnce({ state: "complete", asset });
    queue.add([file()], 1);
    await settle();
    await queue.check(queue.snapshot()[0]!.key);
    expect(request.mock.calls[1]![0]).toMatch(/^\/uploads\/requests\/upload-/);
    expect(request.mock.calls[1]![1]).toBeUndefined();
    expect(complete).toHaveBeenCalledTimes(1);
    expect(complete).toHaveBeenCalledWith(asset);
  });
  it("retains same-key retry after response headers arrived but the body was lost", async () => {
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete);
    request
      .mockRejectedValueOnce(new ApiError(0, "response_unconfirmed", "unreadable body"))
      .mockResolvedValueOnce(asset);
    queue.add([file()], 1);
    await settle();
    const key = queue.snapshot()[0]!.key;
    expect(queue.snapshot()[0]!.retryable).toBe(true);
    await queue.send(key);
    expect(request.mock.calls[1]![1]?.uploadKey).toBe(key);
    expect(complete).toHaveBeenCalledWith(asset);
  });
  it("does not submit concurrently when check/retry are clicked twice", async () => {
    let resolve!: (value: unknown) => void;
    request.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete);
    queue.add([file()], 1);
    const key = queue.snapshot()[0]!.key;
    await queue.check(key);
    await queue.send(key);
    expect(request).toHaveBeenCalledTimes(1);
    resolve(asset);
    await settle();
    expect(complete).toHaveBeenCalledTimes(1);
  });
  it.each(["failed", "expired"])("refuses to resubmit a %s receipt", async (state) => {
    const queue = new UploadQueue(100, vi.fn());
    request.mockRejectedValueOnce(offline()).mockResolvedValueOnce({ state, asset: null });
    queue.add([file()], 1);
    await settle();
    const key = queue.snapshot()[0]!.key;
    await queue.check(key);
    await queue.send(key);
    expect(request).toHaveBeenCalledTimes(2);
    expect(queue.snapshot()[0]!.retryable).toBe(false);
  });
  it("keeps pending uploads visible and inspects without automatic retries", async () => {
    const queue = new UploadQueue(100, vi.fn());
    request.mockRejectedValueOnce(offline()).mockResolvedValueOnce({ state: "pending", asset: null });
    queue.add([file()], 1);
    await settle();
    await queue.check(queue.snapshot()[0]!.key);
    expect(queue.snapshot()[0]!.message).toContain("still pending");
    expect(request).toHaveBeenCalledTimes(2);
  });
  it.each([404, 410, 401])("fails closed when status returns %s", async (status) => {
    const queue = new UploadQueue(100, vi.fn());
    request
      .mockRejectedValueOnce(offline())
      .mockRejectedValueOnce(new ApiError(status, "not_found", "denied"));
    queue.add([file()], 1);
    await settle();
    const key = queue.snapshot()[0]!.key;
    await queue.check(key);
    await queue.send(key);
    expect(request).toHaveBeenCalledTimes(2);
    expect(queue.snapshot()[0]!.retryable).toBe(false);
  });
  it("never reuses an expired request identity", async () => {
    const queue = new UploadQueue(100, vi.fn());
    request.mockRejectedValue(offline());
    queue.add([file()], 1);
    await settle();
    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 24 * 60 * 60 * 1000);
    await queue.send(queue.snapshot()[0]!.key);
    expect(request).toHaveBeenCalledTimes(1);
    expect(queue.snapshot()[0]!.message).toContain("too old");
  });
  it("bounds pending slots and file bytes before sending", async () => {
    request.mockRejectedValue(offline());
    const queue = new UploadQueue(100, vi.fn());
    expect(() => queue.add([file(), file()], 1)).toThrow("up to 1");
    expect(request).not.toHaveBeenCalled();
    queue.add([file()], 1);
    await settle();
    expect(() => queue.add([file()], 1)).toThrow("up to 0");
    expect(() => new UploadQueue(1, vi.fn()).add([file()], 1)).toThrow("smaller");
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("does not reuse an asset already committed to a destination", async () => {
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete);
    request.mockResolvedValueOnce({ ...asset, status: "committed" });
    queue.add([file()], 1);
    await settle();
    expect(complete).not.toHaveBeenCalled();
    expect(queue.snapshot()[0]!.retryable).toBe(false);
  });
  it("dismisses without issuing a delete or starting a fresh upload", async () => {
    const queue = new UploadQueue(100, vi.fn());
    request.mockRejectedValue(offline());
    queue.add([file()], 1);
    await settle();
    queue.dismiss(queue.snapshot()[0]!.key);
    expect(queue.snapshot()).toEqual([]);
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("ignores a late successful response after leaving the view", async () => {
    let resolve!: (value: unknown) => void;
    request.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const complete = vi.fn(),
      queue = new UploadQueue(100, complete);
    queue.add([file()], 1);
    queue.close();
    resolve(asset);
    await settle();
    expect(complete).not.toHaveBeenCalled();
    expect(queue.snapshot()).toEqual([]);
  });
});
