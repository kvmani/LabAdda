// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SearchInput } from "./SearchInput";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

it("synchronises URL navigation without replacing the focused search control", () => {
  const onSearch = vi.fn();
  const { rerender } = render(<SearchInput label="Search people" value="Ben" onSearch={onSearch} />);
  const input = screen.getByRole("searchbox");
  input.focus();
  rerender(<SearchInput label="Search people" value="Chen" onSearch={onSearch} />);
  expect(screen.getByRole("searchbox")).toBe(input);
  expect(document.activeElement).toBe(input);
  expect(input).toHaveProperty("value", "Chen");
});

it("cancels a pending search when its filter scope is removed", () => {
  vi.useFakeTimers();
  const onSearch = vi.fn();
  const { unmount } = render(<SearchInput label="Search people" onSearch={onSearch} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Ben" } });
  unmount();
  vi.runAllTimers();
  expect(onSearch).not.toHaveBeenCalled();
});
