// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { MessageOptions } from "./MessageOptions";

it("preserves thread reading and task actions while hiding restricted contributions", () => {
  const thread = vi.fn();
  const reply = vi.fn();
  const react = vi.fn();
  const view = render(
    <MessageOptions
      canContribute={false}
      onThread={thread}
      onReply={reply}
      onReact={react}
      onShare={vi.fn()}
      onTask={vi.fn()}
    />,
  );
  expect(screen.queryByRole("button", { name: /Reply/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /React/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Open thread/ }));
  expect(thread).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: /Create task/ })).toBeTruthy();
  view.rerender(
    <MessageOptions
      canContribute
      onThread={thread}
      onReply={reply}
      onReact={react}
      onShare={vi.fn()}
      onTask={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /Reply/ }));
  expect(reply).toHaveBeenCalledOnce();
  view.unmount();
});
