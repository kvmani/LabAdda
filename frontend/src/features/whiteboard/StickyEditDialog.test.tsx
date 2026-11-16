// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StickyEditDialog } from "./StickyEditDialog";
import type { StickyConfig } from "./types";

it("retains a typed draft across parent redraws and saves selected font properties", () => {
  const save = vi.fn();
  const close = vi.fn();
  const initial: StickyConfig = { text: "", shape: "rectangle", size: "medium", color: "#fff59d" };
  const view = render(<StickyEditDialog open initialConfig={initial} onClose={close} onSave={save} />);
  fireEvent.change(screen.getByLabelText("Note text"), { target: { value: "Tensile test discussion" } });
  view.rerender(<StickyEditDialog open initialConfig={{ ...initial }} onClose={close} onSave={save} />);
  expect(screen.getByLabelText<HTMLTextAreaElement>("Note text").value).toBe("Tensile test discussion");
  fireEvent.change(screen.getByLabelText("Font", { exact: true }), { target: { value: "handwritten" } });
  fireEvent.change(screen.getByLabelText("Font size", { exact: true }), { target: { value: "24" } });
  view.rerender(
    <StickyEditDialog open canEdit={false} initialConfig={{ ...initial }} onClose={close} onSave={save} />,
  );
  expect(screen.queryByRole("button", { name: "Save note" })).toBeNull();
  expect(screen.getByLabelText<HTMLTextAreaElement>("Note text").value).toBe("Tensile test discussion");
  view.rerender(<StickyEditDialog open initialConfig={{ ...initial }} onClose={close} onSave={save} />);
  fireEvent.click(screen.getByRole("button", { name: "Save note" }));
  expect(save).toHaveBeenCalledWith({
    ...initial,
    text: "Tensile test discussion",
    font_family: "handwritten",
    font_size: 24,
  });
  view.unmount();
});
