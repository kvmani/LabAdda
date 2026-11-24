// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { useFilterParams } from "./useFilterParams";

const wrapper = ({ children }: { children: ReactNode }) => (
  <MemoryRouter initialEntries={["/admin/audit?q=browser&group=access&cursor=abc"]}>{children}</MemoryRouter>
);

it("keeps a cleared filter cleared when another is chosen at once", () => {
  const { result } = renderHook(() => useFilterParams(["q", "group", "outcome"], ["cursor"]), { wrapper });
  act(() => {
    result.current.reset();
    result.current.change("outcome", "denied");
  });
  expect(result.current.params.toString()).toBe("outcome=denied");
});

it("drops paging when a filter changes, but not when paging itself changes", () => {
  const { result } = renderHook(() => useFilterParams(["q", "group"], ["cursor"]), { wrapper });
  act(() => result.current.change("cursor", "def"));
  expect(result.current.params.get("cursor")).toBe("def");
  act(() => result.current.change("q", "microscopy"));
  expect(result.current.params.get("cursor")).toBeNull();
  expect(result.current.params.get("group")).toBe("access");
});
