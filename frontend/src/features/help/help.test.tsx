// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { HelpEntryContext, PageHeader } from "../../ui";
import { entryForRoute } from "./screens";
import { searchHelp } from "./search";
import { orderShelves, shelfFor } from "./shelves";
import type { HelpEntry } from "./types";

afterEach(cleanup);

function entry(overrides: Partial<HelpEntry>): HelpEntry {
  return {
    slug: "using/example",
    shelf: "using",
    title: "Example",
    summary: "An example page.",
    audience: "everyone",
    screen: null,
    updated: "2026-11-11",
    headings: [],
    ...overrides,
  };
}

const ENTRIES = [
  entry({ slug: "using/signing-in", title: "Signing in for the first time", summary: "Choose a password." }),
  entry({ slug: "using/tasks", title: "Tasks", summary: "Plan work.", headings: ["Assigning a task"] }),
  entry({ slug: "using/day", title: "My day", screen: "/today" }),
  entry({ slug: "using/tab", title: "Tabs", screen: "/w/:workspaceId/:tab" }),
];

describe("searchHelp", () => {
  it("matches titles, summaries and headings and ranks titles first", () => {
    expect(searchHelp(ENTRIES, "password").map((found) => found.slug)).toEqual(["using/signing-in"]);
    expect(searchHelp(ENTRIES, "assigning").map((found) => found.slug)).toEqual(["using/tasks"]);
    expect(searchHelp(ENTRIES, "task").map((found) => found.slug)).toEqual(["using/tasks"]);
  });

  it("needs every word and returns nothing for an empty query", () => {
    expect(searchHelp(ENTRIES, "password tasks")).toEqual([]);
    expect(searchHelp(ENTRIES, "  ")).toEqual([]);
  });
});

describe("entryForRoute", () => {
  it("finds the page whose screen matches, including parameters", () => {
    expect(entryForRoute(ENTRIES, "/today")?.slug).toBe("using/day");
    expect(entryForRoute(ENTRIES, "/w/abc/chat")?.slug).toBe("using/tab");
    expect(entryForRoute(ENTRIES, "/notes")).toBeNull();
  });

  it("never explains the help centre itself", () => {
    const pages = [entry({ screen: "/help" })];
    expect(entryForRoute(pages, "/help")).toBeNull();
  });
});

describe("shelves", () => {
  it("puts the reader's own shelf first and keeps troubleshooting with the reference shelf", () => {
    expect(orderShelves("admin").map((shelf) => shelf.id)).toEqual([
      "admin",
      "using",
      "stewards",
      "operator",
    ]);
    expect(shelfFor(entry({ shelf: "troubleshooting" }))).toBe("reference");
  });
});

describe("PageHeader help entry", () => {
  it("hands the header's plain link to the shell's help control as its fallback", () => {
    function Entry({ fallback }: { fallback: React.ReactNode }) {
      return <div data-testid="entry">{fallback}</div>;
    }
    render(
      <HelpEntryContext.Provider value={Entry}>
        <PageHeader title="Page" helpHref="/somewhere" />
      </HelpEntryContext.Provider>,
    );
    const link = screen.getByRole("link", { name: "Help with this page" });
    expect(screen.getByTestId("entry").contains(link)).toBe(true);
  });
});
