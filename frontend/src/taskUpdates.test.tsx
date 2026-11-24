// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { RealtimeEvent } from "./realtime";

const handlers = new Map<string, (event: RealtimeEvent) => void>();
vi.mock("./realtime", async (original) => ({
  ...(await original<typeof import("./realtime")>()),
  realtime: {
    subscribe: (id: string, handler: (event: RealtimeEvent) => void) => {
      handlers.set(id, handler);
      return () => handlers.delete(id);
    },
  },
}));

const { useTaskUpdates } = await import("./taskUpdates");

afterEach(() => handlers.clear());

const send = (id: string, event: RealtimeEvent) => act(() => handlers.get(id)?.(event));

it("reports a first confirmation without raising a notice, and a later one as missed work", () => {
  const confirmed = vi.fn();
  const { result } = renderHook(() => useTaskUpdates(["a", "b"], undefined, confirmed));
  send("a", { type: "subscribed", workspace_id: "a" });
  expect(confirmed).toHaveBeenCalledTimes(1);
  expect(result.current.pending).toBe(false);
  send("a", { type: "subscribed", workspace_id: "a" });
  expect(confirmed).toHaveBeenCalledTimes(1);
  expect(result.current.pending).toBe(true);
});

it("keeps a change that arrives during a fetch pending after that fetch", () => {
  const { result } = renderHook(() => useTaskUpdates(["a"]));
  const seen = result.current.snapshot();
  send("a", { type: "tasks.changed", workspace_id: "a" });
  act(() => result.current.acknowledge(seen));
  expect(result.current.pending).toBe(true);
});

it("treats loss of access as a change and tells the screen", () => {
  const denied = vi.fn();
  const { result } = renderHook(() => useTaskUpdates(["a"], denied));
  send("a", { type: "revoked", workspace_id: "a" });
  expect(denied).toHaveBeenCalled();
  expect(result.current.pending).toBe(true);
});
