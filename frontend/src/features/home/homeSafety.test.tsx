// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { api } from "../../api";
import { dayRange, siteDay } from "./homeDates";
import { useHomePanels } from "./useHomePanels";
import { useHomeTasks } from "./useHomeTasks";
import type { Work } from "./useDashboardOverview";

vi.mock("../../api", () => ({ api: vi.fn(), errorMessage: (error: unknown) => String(error) }));
beforeEach(() => vi.resetAllMocks());
const work: Work = {
  id: "task",
  list_id: "list",
  list_title: "Research plan",
  workspace_id: null,
  workspace_name: null,
  title: "Calibrate",
  due_date: null,
  priority: "high",
  status: "blocked",
};
const current = {
  id: "task",
  title: "Calibrate",
  description: "Preserve this text",
  due_date: null,
  priority: "high",
  checklist: [],
  revision: 3,
  status: "blocked",
  done: false,
};

test("day bounds use site timezone and daylight-saving day length", () => {
  expect(siteDay(new Date("2026-11-16T20:00:00Z"), "Asia/Kolkata")).toBe("2026-11-17");
  expect(dayRange("2026-11-17", "Asia/Kolkata")).toEqual({
    start: "2026-11-16T18:30:00.000Z",
    end: "2026-11-17T18:30:00.000Z",
  });
  for (const [day, hours] of [
    ["2026-03-08", 23],
    ["2026-11-01", 25],
  ] as const) {
    const range = dayRange(day, "America/New_York");
    expect(Date.parse(range.end) - Date.parse(range.start)).toBe(hours * 3600000);
  }
});

test("completion waits for save; undo preserves prior status and saved revision", async () => {
  let finish: (value: unknown) => void = () => {};
  vi.mocked(api)
    .mockResolvedValueOnce(current)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
  const refresh = vi.fn().mockResolvedValue(undefined);
  const { result } = renderHook(() => useHomeTasks(refresh, "scope"));
  let pending: Promise<void> = Promise.resolve();
  act(() => {
    pending = result.current.toggle(work);
  });
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  expect(result.current.notice).toBeNull();
  await act(async () => {
    finish({ ...current, status: "done", done: true, revision: 4 });
    await pending;
  });
  expect(result.current.notice?.previous).toBe("blocked");
  vi.mocked(api).mockRejectedValueOnce(new Error("Task changed. Refresh before editing."));
  await act(() => result.current.undo());
  expect(api).toHaveBeenLastCalledWith("/todos/lists/list/tasks/task", {
    method: "PUT",
    body: {
      title: current.title,
      description: current.description,
      due_date: null,
      priority: "high",
      checklist: [],
      status: "blocked",
      revision: 4,
      done: false,
    },
  });
  expect(result.current.error).toContain("Task changed");
  expect(result.current.notice).not.toBeNull();
});

test("failed completion never announces success, and access changes discard late saves", async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error("Offline"));
  const { result, rerender } = renderHook(
    ({ scope }) => useHomeTasks(vi.fn().mockResolvedValue(undefined), scope),
    { initialProps: { scope: "old" } },
  );
  await act(() => result.current.toggle(work));
  expect(result.current.notice).toBeNull();
  expect(result.current.error).toContain("Offline");
  let finish: (value: unknown) => void = () => {};
  vi.mocked(api)
    .mockResolvedValueOnce(current)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
  let pending: Promise<void> = Promise.resolve();
  act(() => {
    pending = result.current.toggle(work);
  });
  await waitFor(() => expect(api).toHaveBeenCalledTimes(3));
  rerender({ scope: "new" });
  await act(async () => {
    finish({ ...current, status: "done", revision: 4 });
    await pending;
  });
  expect(result.current.notice).toBeNull();
});

test("late agenda replies cannot restore an older access scope", async () => {
  let finish: (value: unknown) => void = () => {};
  vi.mocked(api).mockImplementation((path) => {
    if (path === "/notes") return Promise.resolve({ notes: [] });
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const { result, rerender } = renderHook(({ scope }) => useHomePanels(scope, "2026-11-17", "Asia/Kolkata"), {
    initialProps: { scope: "old" },
  });
  const oldResponse = finish;
  rerender({ scope: "new" });
  await act(async () => {
    oldResponse([{ id: "event", title: "Revoked workspace agenda" }]);
    await Promise.resolve();
  });
  expect(result.current.events).toEqual([]);
});
