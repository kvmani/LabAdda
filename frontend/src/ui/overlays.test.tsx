// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";
import { Dialog } from "./Dialog";
import { Drawer } from "./Drawer";
import { Menu } from "./Menu";
import { TOAST_MILLISECONDS, ToastProvider, useToast } from "./Toast";
import { Tooltip } from "./Tooltip";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function DialogHarness({ kind }: { kind: "dialog" | "drawer" }) {
  const [open, setOpen] = useState(false);
  const Surface = kind === "dialog" ? Dialog : Drawer;
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open details</Button>
      <Surface
        open={open}
        title="Asha Rao"
        onClose={() => setOpen(false)}
        footer={<Button onClick={() => setOpen(false)}>Done</Button>}
      >
        <a href="#record">Record</a>
      </Surface>
    </>
  );
}

describe.each(["dialog", "drawer"] as const)("%s", (kind) => {
  it("is a named modal that traps Tab, closes on Escape and restores focus", async () => {
    render(<DialogHarness kind={kind} />);
    const opener = screen.getByRole("button", { name: "Open details" });
    await userEvent.click(opener);
    const surface = screen.getByRole("dialog", { name: "Asha Rao" });
    expect(surface.getAttribute("aria-modal")).toBe("true");
    const close = screen.getByRole("button", { name: kind === "dialog" ? "Close" : "Close panel" });
    const done = screen.getByRole("button", { name: "Done" });
    expect(document.activeElement).toBe(close);

    await userEvent.tab();
    expect(document.activeElement).toBe(screen.getByRole("link", { name: "Record" }));
    await userEvent.tab();
    expect(document.activeElement).toBe(done);
    await userEvent.tab();
    expect(document.activeElement).toBe(close);
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(done);

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });
});

describe("ConfirmDialog", () => {
  function Harness({ onConfirm }: { onConfirm: (reason: string) => Promise<void> }) {
    const [open, setOpen] = useState(true);
    return (
      <ConfirmDialog
        open={open}
        title="Retire Deepa Iyer?"
        consequences={["Deepa Iyer can no longer sign in.", "Surface Engineering Division needs a new Head."]}
        confirmLabel="Retire 1 person"
        requireReason
        danger
        onConfirm={async (reason) => {
          await onConfirm(reason);
          setOpen(false);
        }}
        onCancel={() => setOpen(false)}
      />
    );
  }

  it("names the consequences and needs a reason before confirming", async () => {
    const onConfirm = vi.fn(() => Promise.resolve());
    render(<Harness onConfirm={onConfirm} />);
    expect(screen.getByText("Deepa Iyer can no longer sign in.")).toBeTruthy();
    const confirm = screen.getByRole("button", { name: "Retire 1 person" });
    expect(confirm).toHaveProperty("disabled", true);
    const reason = screen.getByRole("textbox", { name: "Reason (required)" });
    expect(document.activeElement).toBe(reason);
    await userEvent.type(reason, "  Retired on 30 November  ");
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith("Retired on 30 November");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("stays open with the error and the reason when the action fails", async () => {
    const onConfirm = vi.fn(() =>
      Promise.reject(new Error("This record changed. Reload and review it again.")),
    );
    render(<Harness onConfirm={onConfirm} />);
    await userEvent.type(screen.getByRole("textbox", { name: "Reason (required)" }), "Retirement");
    await userEvent.click(screen.getByRole("button", { name: "Retire 1 person" }));
    expect(screen.getByRole("alert").textContent).toBe("This record changed. Reload and review it again.");
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Reason (required)" }).value).toBe(
      "Retirement",
    );
  });
});

describe("Menu", () => {
  it("opens from the keyboard, moves with arrows, chooses with Enter and returns focus", async () => {
    const transfer = vi.fn();
    const retire = vi.fn();
    render(
      <Menu
        label="Actions for Bharat"
        items={[
          { label: "Transfer", onSelect: transfer },
          { label: "Promote", onSelect: () => undefined, disabled: true },
          { label: "Retire", onSelect: retire, danger: true },
        ]}
      />,
    );
    const trigger = screen.getByRole("button", { name: "Actions for Bharat" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    trigger.focus();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("menu", { name: "Actions for Bharat" })).toBeTruthy();
    expect(document.activeElement?.textContent).toBe("Transfer");
    await userEvent.keyboard("{ArrowDown}");
    expect(document.activeElement?.textContent).toBe("Retire");
    await userEvent.keyboard("{Enter}");
    expect(retire).toHaveBeenCalledOnce();
    expect(transfer).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("closes on Escape without choosing", async () => {
    const transfer = vi.fn();
    render(<Menu label="Actions" items={[{ label: "Transfer", onSelect: transfer }]} />);
    await userEvent.click(screen.getByRole("button", { name: "Actions" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(transfer).not.toHaveBeenCalled();
  });
});

describe("Tooltip", () => {
  it("describes its trigger, shows on focus and hides on Escape", async () => {
    render(
      <Tooltip text="A steward looks after a workspace.">
        <button type="button">Steward</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole("button", { name: "Steward" });
    const tip = document.getElementById(trigger.getAttribute("aria-describedby") ?? "");
    expect(tip?.textContent).toBe("A steward looks after a workspace.");
    expect(tip?.hidden).toBe(true);
    await userEvent.tab();
    expect(tip?.hidden).toBe(false);
    await userEvent.keyboard("{Escape}");
    expect(tip?.hidden).toBe(true);
  });
});

describe("Toast", () => {
  function Saver() {
    const toast = useToast();
    return <Button onClick={() => toast("Note saved.")}>Save</Button>;
  }

  it("announces a confirmation, can be dismissed and disappears on its own", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Saver />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("status").textContent).toContain("Note saved.");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss message" }));
    expect(screen.getByRole("status").textContent).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    act(() => {
      vi.advanceTimersByTime(TOAST_MILLISECONDS);
    });
    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("refuses to work outside its provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Saver />)).toThrow("useToast must be used inside ToastProvider");
  });
});

describe("Menu with a shorter visible label", () => {
  it("keeps the visible text inside the accessible name", () => {
    render(<Menu label="Account menu for Asha Rao" visibleLabel="Asha Rao" items={[]} />);
    const trigger = screen.getByRole("button", { name: "Account menu for Asha Rao" });
    expect(trigger.textContent).toBe("Asha Rao");
  });
});
