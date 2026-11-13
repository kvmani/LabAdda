// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Breadcrumbs } from "./Breadcrumbs";
import { DataTable, type Column } from "./DataTable";
import { Stepper } from "./Stepper";
import { Tabs } from "./Tabs";
import { TreeView, visibleItems, type TreeNode } from "./TreeView";

afterEach(cleanup);

describe("Tabs", () => {
  function Harness() {
    const [selected, setSelected] = useState("record");
    return (
      <Tabs
        label="Person details"
        selected={selected}
        onSelect={setSelected}
        tabs={[
          { id: "record", label: "Record" },
          { id: "access", label: "Access" },
          { id: "timeline", label: "Timeline" },
        ]}
      >
        Showing {selected}
      </Tabs>
    );
  }

  it("has one tab stop and moves selection with arrows, Home and End", async () => {
    render(<Harness />);
    const record = screen.getByRole("tab", { name: "Record" });
    expect(record.getAttribute("aria-selected")).toBe("true");
    expect(screen.getAllByRole("tab").filter((tab) => tab.tabIndex === 0)).toHaveLength(1);
    record.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Access" }));
    expect(screen.getByRole("tabpanel", { name: "Access" }).textContent).toBe("Showing access");
    await userEvent.keyboard("{End}");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Timeline" }));
    await userEvent.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(record);
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Timeline" }).getAttribute("aria-selected")).toBe("true");
  });
});

describe("Breadcrumbs", () => {
  it("links each ancestor and marks the current page", () => {
    render(
      <MemoryRouter>
        <Breadcrumbs
          items={[
            { label: "Administration", to: "/admin" },
            { label: "People", to: "/admin/people" },
            { label: "Asha Rao" },
          ]}
        />
      </MemoryRouter>,
    );
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Administration", "People"]);
    expect(within(nav).getByText("Asha Rao").getAttribute("aria-current")).toBe("page");
  });
});

describe("Stepper", () => {
  it("states the current step in words", () => {
    render(<Stepper steps={["Choose unit", "Options", "Review", "Done"]} current={2} />);
    expect(screen.getByText("Step 3 of 4: Review")).toBeTruthy();
    expect(screen.getByText("Review").closest("li")?.getAttribute("aria-current")).toBe("step");
    expect(screen.getByText("Choose unit").closest("li")?.textContent).toContain("(done)");
  });
});

type Person = { id: string; name: string; staff: number };
const people: Person[] = [
  { id: "1", name: "Chitra", staff: 30 },
  { id: "2", name: "asha", staff: 4 },
  { id: "3", name: "Bharat", staff: 12 },
];
const columns: Column<Person>[] = [
  { key: "name", header: "Name", render: (row) => row.name, sortValue: (row) => row.name },
  { key: "staff", header: "Staff", render: (row) => row.staff, sortValue: (row) => row.staff, align: "end" },
  { key: "id", header: "ID", render: (row) => row.id },
];
const names = () =>
  screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0]?.textContent);

describe("DataTable", () => {
  it("is a named, focusable region with a caption", () => {
    render(<DataTable caption="People" columns={columns} rows={people} rowKey={(row) => row.id} />);
    const region = screen.getByRole("region", { name: "People" });
    expect(region.tabIndex).toBe(0);
    expect(screen.getByRole("table", { name: "People" })).toBeTruthy();
  });

  it("sorts by a column, toggles direction and announces it", async () => {
    render(<DataTable caption="People" columns={columns} rows={people} rowKey={(row) => row.id} />);
    const nameHeader = screen.getByRole("columnheader", { name: "Name" });
    expect(nameHeader.getAttribute("aria-sort")).toBe("none");
    expect(screen.getByRole("columnheader", { name: "ID" }).getAttribute("aria-sort")).toBeNull();
    await userEvent.click(within(nameHeader).getByRole("button", { name: "Name" }));
    expect(names()).toEqual(["asha", "Bharat", "Chitra"]);
    expect(nameHeader.getAttribute("aria-sort")).toBe("ascending");
    expect(screen.getByRole("status").textContent).toBe("Sorted by Name, ascending");
    within(nameHeader).getByRole("button", { name: "Name" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(names()).toEqual(["Chitra", "Bharat", "asha"]);
    expect(screen.getByRole("status").textContent).toBe("Sorted by Name, descending");
    await userEvent.click(screen.getByRole("button", { name: "Staff" }));
    expect(names()).toEqual(["asha", "Bharat", "Chitra"]);
  });

  it("shows loading and empty states instead of the table", () => {
    const { rerender } = render(
      <DataTable caption="People" columns={columns} rows={[]} rowKey={(row) => row.id} loading />,
    );
    expect(screen.getByRole("status").textContent).toBe("Loading people…");
    rerender(
      <DataTable
        caption="People"
        columns={columns}
        rows={[]}
        rowKey={(row) => row.id}
        empty={{ title: "No people match these filters" }}
      />,
    );
    expect(screen.getByText("No people match these filters")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

const org: TreeNode[] = [
  {
    id: "root",
    label: "Institute",
    children: [
      {
        id: "division",
        label: "Surface Engineering Division",
        children: [
          { id: "a", label: "Thin Films" },
          { id: "b", label: "Corrosion" },
        ],
      },
      { id: "admin", label: "Administration" },
    ],
  },
];

describe("TreeView", () => {
  it("lists only visible nodes in order with their level", () => {
    const items = visibleItems(org, new Set(["root"]));
    expect(items.map((item) => [item.node.id, item.level, item.position, item.setSize])).toEqual([
      ["root", 1, 1, 1],
      ["division", 2, 1, 2],
      ["admin", 2, 2, 2],
    ]);
  });

  it("is fully operable from the keyboard", async () => {
    const onSelect = vi.fn();
    render(<TreeView label="Organisation" nodes={org} onSelect={onSelect} initiallyExpanded={["root"]} />);
    const root = screen.getByRole("treeitem", { name: "Institute" });
    expect(root.getAttribute("aria-expanded")).toBe("true");
    root.focus();
    await userEvent.keyboard("{ArrowDown}");
    const division = screen.getByRole("treeitem", { name: "Surface Engineering Division" });
    expect(document.activeElement).toBe(division);
    expect(division.getAttribute("aria-expanded")).toBe("false");
    await userEvent.keyboard("{ArrowRight}");
    expect(division.getAttribute("aria-expanded")).toBe("true");
    await userEvent.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: "Thin Films" }));
    expect(document.activeElement?.getAttribute("aria-level")).toBe("3");
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenLastCalledWith(expect.objectContaining({ id: "a" }));
    await userEvent.keyboard("{ArrowLeft}");
    expect(document.activeElement).toBe(division);
    await userEvent.keyboard("{ArrowLeft}");
    expect(division.getAttribute("aria-expanded")).toBe("false");
    await userEvent.keyboard("{End}");
    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: "Administration" }));
    await userEvent.keyboard("{Home}");
    expect(document.activeElement).toBe(root);
  });

  it("marks the selected node and keeps a single tab stop", () => {
    render(
      <TreeView
        label="Organisation"
        nodes={org}
        onSelect={() => undefined}
        selectedId="admin"
        initiallyExpanded={["root"]}
      />,
    );
    const selected = screen.getByRole("treeitem", { name: "Administration", selected: true });
    expect(selected.tabIndex).toBe(0);
    expect(screen.getAllByRole("treeitem").filter((item) => item.tabIndex === 0)).toHaveLength(1);
  });
});
