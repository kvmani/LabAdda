// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { IconButton } from "./IconButton";

afterEach(cleanup);

describe("Button", () => {
  it("is a plain button named by its text and activates by keyboard", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save note</Button>);
    const button = screen.getByRole("button", { name: "Save note" });
    expect(button.getAttribute("type")).toBe("button");
    button.focus();
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard(" ");
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("is disabled and says so while busy", async () => {
    const onClick = vi.fn();
    render(
      <Button busy busyLabel="Saving…" onClick={onClick}>
        Save note
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Saving…" });
    expect(button).toHaveProperty("disabled", true);
    expect(button.getAttribute("aria-busy")).toBe("true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("can submit a form when asked", async () => {
    const onSubmit = vi.fn((event: Event) => event.preventDefault());
    render(
      <form onSubmit={(event) => onSubmit(event.nativeEvent)}>
        <Button type="submit">Create list</Button>
      </form>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Create list" }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});

describe("IconButton", () => {
  it("uses its label as the accessible name and hover hint", () => {
    render(<IconButton icon="close" label="Close dialog" />);
    const button = screen.getByRole("button", { name: "Close dialog" });
    expect(button.getAttribute("title")).toBe("Close dialog");
  });
});

describe("Icon", () => {
  it("is hidden from assistive technology unless labelled", () => {
    const { container } = render(<Icon name="check" />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    render(<Icon name="warning" label="Warning" />);
    expect(screen.getByRole("img", { name: "Warning" })).toBeTruthy();
  });
});
