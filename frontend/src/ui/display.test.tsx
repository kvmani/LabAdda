// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Avatar, initials, toneFor } from "./Avatar";
import { Badge } from "./Badge";
import { Banner } from "./Banner";
import { Button } from "./Button";
import { Card } from "./Card";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { PageHeader } from "./PageHeader";
import { Skeleton } from "./Skeleton";
import { StatTile } from "./StatTile";
import { StatusPill, type HealthStatus } from "./StatusPill";
import { Tag } from "./Tag";

afterEach(cleanup);

describe("Card", () => {
  it("is a region named by its heading at the requested level", () => {
    render(
      <Card title="Accounts" level={3} actions={<Button>Add person</Button>}>
        Body
      </Card>,
    );
    expect(screen.getByRole("region", { name: "Accounts" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3, name: "Accounts" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add person" })).toBeTruthy();
  });
});

describe("PageHeader", () => {
  it("has one page heading, the scope line and a help link", () => {
    render(<PageHeader title="People" scope="Everyone in the organisation" helpHref="/help/admin/people" />);
    expect(screen.getByRole("heading", { level: 1, name: "People" })).toBeTruthy();
    expect(screen.getByText("Everyone in the organisation")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Help with this page" }).getAttribute("href")).toBe(
      "/help/admin/people",
    );
  });
});

describe("Badge", () => {
  it("reads the full count with its meaning and caps the visible number", () => {
    const { container } = render(<Badge count={120} label="unread messages" />);
    expect(screen.getByText("120 unread messages")).toBeTruthy();
    expect(container.querySelector("[aria-hidden='true']")?.textContent).toBe("99+");
  });

  it("renders nothing for zero", () => {
    const { container } = render(<Badge count={0} label="unread messages" />);
    expect(container.innerHTML).toBe("");
  });
});

describe("StatusPill and Tag", () => {
  it("states every health status in words", () => {
    const words: Record<HealthStatus, string> = {
      healthy: "Healthy",
      degraded: "Degraded",
      unavailable: "Unavailable",
      stale: "Stale",
      unknown: "Unknown",
      unsupported: "Not supported",
    };
    for (const [status, word] of Object.entries(words)) {
      render(<StatusPill status={status as HealthStatus} />);
      expect(screen.getByText(word)).toBeTruthy();
    }
  });

  it("accepts a custom label and tone", () => {
    render(
      <>
        <StatusPill tone="warn" icon="clock" label="On leave" />
        <Tag tone="danger">Suspended</Tag>
      </>,
    );
    expect(screen.getByText("On leave")).toBeTruthy();
    expect(screen.getByText("Suspended").className).toContain("ui-tag--danger");
  });
});

describe("Avatar", () => {
  it("shows up to two initials and is hidden from screen readers", () => {
    expect(initials("Asha Rao")).toBe("AR");
    expect(initials("bharat")).toBe("B");
    expect(initials("  Chitra  Iyer  Rao ")).toBe("CR");
    expect(initials("")).toBe("?");
    const { container } = render(<Avatar id="u1" name="Asha Rao" />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
  });

  it("gives the same person the same tone every time", () => {
    expect(toneFor("user-123")).toBe(toneFor("user-123"));
  });
});

describe("EmptyState, ErrorState and Skeleton", () => {
  it("teaches the first step when empty", () => {
    render(
      <EmptyState title="No lists yet" action={<Button>Create a list</Button>}>
        Lists you create here are shared with this section.
      </EmptyState>,
    );
    expect(screen.getByText("No lists yet")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create a list" })).toBeTruthy();
  });

  it("announces a failure and retries from the keyboard", async () => {
    const onRetry = vi.fn();
    render(<ErrorState message="The server did not answer. Check your connection." onRetry={onRetry} />);
    expect(screen.getByRole("alert").textContent).toContain("The server did not answer.");
    screen.getByRole("button", { name: "Try again" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("announces loading with a label", () => {
    render(<Skeleton lines={2} label="Loading people…" />);
    expect(screen.getByRole("status").textContent).toBe("Loading people…");
  });
});

describe("Banner", () => {
  it("is a status message that shows markup as plain text and names its level", () => {
    const { container } = render(<Banner level="warning">{"<b>Back at 6</b>"}</Banner>);
    expect(screen.getByRole("status").textContent).toContain("Warning: <b>Back at 6</b>");
    expect(container.querySelector("b")).toBeNull();
  });
});

describe("StatTile", () => {
  it("links its label to the detail page and shows the figure, status and note", () => {
    render(
      <MemoryRouter>
        <StatTile
          label="Last backup"
          value="5 h ago"
          status="degraded"
          note="Updated 3 s ago"
          to="/admin/backups"
        >
          <span>trend</span>
        </StatTile>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Last backup" }).getAttribute("href")).toBe("/admin/backups");
    expect(screen.getByText("5 h ago")).toBeTruthy();
    expect(screen.getByText("Degraded")).toBeTruthy();
    expect(screen.getByText("Updated 3 s ago")).toBeTruthy();
    expect(screen.getByText("trend")).toBeTruthy();
  });
});
