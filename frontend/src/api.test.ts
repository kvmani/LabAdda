import { afterEach, describe, expect, it, vi } from "vitest";
import {
  accessDenied,
  api,
  ApiError,
  errorCode,
  errorMessage,
  errorStatus,
  outcomeUnknown,
  setCsrf,
} from "./api";
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrf(null);
});
describe("upload transport contract", () => {
  it("sends explicit upload identity with CSRF and the original multipart form", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response('{"id":"fixture"}', { status: 201, headers: { "content-type": "application/json" } }),
      );
    vi.stubGlobal("fetch", fetcher);
    setCsrf("synthetic-csrf");
    const form = new FormData();
    form.append("file", new Blob(["fixture"]), "fixture.pdf");
    expect(await api("/uploads", { form, uploadKey: "synthetic-request-01" })).toEqual({ id: "fixture" });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/uploads",
      expect.objectContaining({
        body: form,
        credentials: "same-origin",
        headers: expect.objectContaining({
          "Idempotency-Key": "synthetic-request-01",
          "X-CSRF-Token": "synthetic-csrf",
        }),
      }),
    );
  });
  it.each(["truncated", "body-lost", "wrong-type"])(
    "treats a %s successful response as uncertain",
    async (kind) => {
      const response = new Response(kind === "truncated" ? "{" : "<html>proxy</html>", {
        status: 201,
        headers: { "content-type": kind === "wrong-type" ? "text/html" : "application/json" },
      });
      if (kind === "body-lost")
        response.json = () => Promise.reject(new TypeError("synthetic connection reset"));
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
      await expect(
        api("/uploads", { form: new FormData(), uploadKey: "synthetic-request-01" }),
      ).rejects.toMatchObject({ code: "response_unconfirmed", status: 0 });
    },
  );
  it("preserves uniform server denial instead of retrying it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"error":{"code":"not_found","message":"Not found."}}', {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    await expect(api("/uploads/requests/synthetic-request-01")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("error helpers", () => {
  it("recognise access denial only from API errors", () => {
    for (const status of [401, 403, 404])
      expect(accessDenied(new ApiError(status, "denied", "x"))).toBe(true);
    expect(accessDenied(new ApiError(409, "conflict", "x"))).toBe(false);
    // A plain object is not an API error; callers must construct ApiError (see pages/Todos.tsx).
    expect(accessDenied({ status: 404 })).toBe(false);
  });

  it("treat no reply and server failures as unknown outcomes", () => {
    expect(outcomeUnknown(new ApiError(0, "offline", "x"))).toBe(true);
    expect(outcomeUnknown(new ApiError(503, "unavailable", "x"))).toBe(true);
    expect(outcomeUnknown(new ApiError(422, "invalid", "x"))).toBe(false);
    expect(outcomeUnknown(new Error("x"))).toBe(false);
  });

  it("show the message of any error and a fallback otherwise", () => {
    expect(errorMessage(new ApiError(404, "not_found", "Not found."))).toBe("Not found.");
    expect(errorMessage("text")).toBe("Something went wrong. Try again.");
    expect(errorStatus(new Error("x"))).toBeUndefined();
    expect(errorCode(new ApiError(409, "stale_revision", "x"))).toBe("stale_revision");
  });
});

describe("metadata report transport", () => {
  it("returns CSV bytes while keeping the authenticated transport", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response("username\nben\n", {
        headers: { "content-type": "text/csv; charset=utf-8" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    const report = await api<Blob>("/admin/people/export.csv", { responseType: "blob" });
    expect(await report.text()).toBe("username\nben\n");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/admin/people/export.csv",
      expect.objectContaining({
        credentials: "same-origin",
      }),
    );
  });

  it("keeps structured access denial instead of downloading an error as CSV", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: "forbidden", message: "Administrator access required." },
          }),
          { status: 403, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    await expect(api("/admin/people/export.csv", { responseType: "blob" })).rejects.toMatchObject({
      status: 403,
      code: "forbidden",
      message: "Administrator access required.",
    });
  });
});
