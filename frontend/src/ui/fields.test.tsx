// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Checkbox } from "./Checkbox";
import { DateInput } from "./DateInput";
import { SearchInput } from "./SearchInput";
import { Select } from "./Select";
import { Switch } from "./Switch";
import { TextArea } from "./TextArea";
import { TextInput } from "./TextInput";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("TextInput", () => {
  it("is named by its label and described by its hint and error", () => {
    render(<TextInput label="Display name" hint="As colleagues see it" error="Enter a name." required />);
    const input = screen.getByRole("textbox", { name: "Display name (required)" });
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const described = (input.getAttribute("aria-describedby") ?? "").split(" ");
    const texts = described.map((id) => document.getElementById(id)?.textContent);
    expect(texts).toEqual(["As colleagues see it", "Enter a name."]);
    expect(screen.getByRole("alert").textContent).toBe("Enter a name.");
  });

  it("is not marked invalid without an error", () => {
    render(<TextInput label="Username" />);
    expect(screen.getByRole("textbox", { name: "Username" }).getAttribute("aria-invalid")).toBeNull();
  });
});

describe("TextArea, Select and DateInput", () => {
  it("are named by their labels", () => {
    render(
      <>
        <TextArea label="Reason" />
        <Select label="Role" placeholder="Choose a role" options={[{ value: "member", label: "Member" }]} />
        <DateInput label="Effective date" />
      </>,
    );
    expect(screen.getByRole("textbox", { name: "Reason" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Role" })).toBeTruthy();
    expect(screen.getByLabelText("Effective date").getAttribute("type")).toBe("date");
  });

  it("lets the keyboard choose an option", async () => {
    const onChange = vi.fn();
    render(
      <Select
        label="Role"
        options={[
          { value: "member", label: "Member" },
          { value: "steward", label: "Steward" },
        ]}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />,
    );
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Role" }), "steward");
    expect(onChange).toHaveBeenCalledWith("steward");
  });
});

describe("Checkbox", () => {
  it("toggles from its label and with the space bar", async () => {
    render(<Checkbox label="Keep access during handover" />);
    const box = screen.getByRole("checkbox", { name: "Keep access during handover" });
    await userEvent.click(screen.getByText("Keep access during handover"));
    expect(box).toHaveProperty("checked", true);
    box.focus();
    await userEvent.keyboard(" ");
    expect(box).toHaveProperty("checked", false);
  });
});

describe("Switch", () => {
  function Controlled() {
    const [on, setOn] = useState(false);
    return <Switch label="Mention alerts" checked={on} onChange={setOn} />;
  }

  it("is a named switch that toggles by keyboard and shows its state as text", async () => {
    render(<Controlled />);
    const control = screen.getByRole("switch", { name: "Mention alerts" });
    expect(control.getAttribute("aria-checked")).toBe("false");
    expect(control.textContent).toContain("Off");
    control.focus();
    await userEvent.keyboard("{Enter}");
    expect(control.getAttribute("aria-checked")).toBe("true");
    expect(control.textContent).toContain("On");
  });
});

describe("SearchInput", () => {
  it("searches once typing pauses, clears with Escape, and announces the result count", () => {
    vi.useFakeTimers();
    const onSearch = vi.fn();
    const { rerender } = render(<SearchInput label="Search people" onSearch={onSearch} delay={300} />);
    const input = screen.getByRole("searchbox", { name: "Search people" });
    fireEvent.change(input, { target: { value: "as" } });
    fireEvent.change(input, { target: { value: " asha " } });
    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(onSearch).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(onSearch).toHaveBeenCalledOnce();
    expect(onSearch).toHaveBeenLastCalledWith("asha");

    rerender(<SearchInput label="Search people" onSearch={onSearch} delay={300} resultCount={1} />);
    expect(screen.getByRole("status").textContent).toBe("1 result");

    fireEvent.keyDown(input, { key: "Escape" });
    expect(onSearch).toHaveBeenLastCalledWith("");
    expect((input as HTMLInputElement).value).toBe("");
  });

  it("offers a named clear button only when there is text", () => {
    render(<SearchInput label="Search people" onSearch={() => undefined} initialValue="ben" />);
    fireEvent.click(screen.getByRole("button", { name: "Clear search people" }));
    expect(screen.queryByRole("button", { name: "Clear search people" })).toBeNull();
  });
});
