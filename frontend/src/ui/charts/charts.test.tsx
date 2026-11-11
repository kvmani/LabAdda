// @vitest-environment jsdom
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { AreaChart, BarChart, HeatGrid, LineChart, Meter, Sparkline, type Series } from "..";

afterEach(cleanup);

const HOUR = 3_600_000;
const START = Date.UTC(2026, 10, 10, 0, 0);
function focusPlot() {
  act(() => screen.getByRole("application").focus());
}
const hourly = (values: (number | null)[]) => values.map((value, i) => ({ t: START + i * HOUR, value }));
const LATENCY: Series = { label: "Latency", points: hourly([20, 24, 22, 30]) };
const COMMON = { title: "Response time", unit: "ms", period: "Last 4 hours", updated: "Updated 12 s ago" };

describe("LineChart", () => {
  it("names itself, its period and when it was updated", () => {
    render(<LineChart {...COMMON} series={[LATENCY]} />);
    expect(screen.getByRole("application", { name: /Response time, Last 4 hours/ })).toBeTruthy();
    expect(screen.getByText(/Last 4 hours · Updated 12 s ago/)).toBeTruthy();
  });

  it("says the update time is unknown rather than inventing one", () => {
    render(<LineChart {...COMMON} updated={undefined} series={[LATENCY]} />);
    expect(screen.getByText(/Update time unknown/)).toBeTruthy();
  });

  it("shows an empty state when there is no data, and when every sample is a gap", () => {
    const { rerender } = render(<LineChart {...COMMON} series={[]} />);
    expect(screen.getByText("No data for this period")).toBeTruthy();
    rerender(<LineChart {...COMMON} series={[{ label: "Latency", points: hourly([null, null]) }]} />);
    expect(screen.getByText("No data for this period")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "View as table" })).toBeNull();
  });

  it("draws a single point as a mark, without a line", () => {
    const { container } = render(
      <LineChart {...COMMON} series={[{ label: "Latency", points: hourly([25]) }]} />,
    );
    expect(container.querySelectorAll(".ui-chart__mark")).toHaveLength(1);
    expect(container.querySelector(".ui-chart__line")?.getAttribute("d")).toBe("");
  });

  it("breaks the line at a gap instead of drawing zero", () => {
    const series = [{ label: "Latency", points: hourly([20, 22, null, 28, 30]) }];
    const { container } = render(<LineChart {...COMMON} series={series} />);
    const path = container.querySelector(".ui-chart__line")?.getAttribute("d") ?? "";
    expect(path.match(/M/g)).toHaveLength(2);
  });

  it("reads points with the arrow keys, announcing label, time and value with unit", async () => {
    render(<LineChart {...COMMON} series={[LATENCY]} />);
    const plot = screen.getByRole("application");
    focusPlot();
    expect(document.activeElement).toBe(plot);
    const status = screen.getByRole("status");
    expect(status.textContent).toMatch(/^Latency, .*, 20 ms$/);
    await userEvent.keyboard("{ArrowRight}");
    expect(status.textContent).toMatch(/24 ms$/);
    await userEvent.keyboard("{End}");
    expect(status.textContent).toMatch(/30 ms$/);
    await userEvent.keyboard("{ArrowRight}");
    expect(status.textContent).toMatch(/30 ms$/);
    await userEvent.keyboard("{Escape}");
    expect(status.textContent).toBe("");
  });

  it("announces a gap as no data", async () => {
    render(<LineChart {...COMMON} series={[{ label: "Latency", points: hourly([20, null]) }]} />);
    focusPlot();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("status").textContent).toMatch(/no data$/);
  });

  it("switches series with up and down and shows a legend only for several series", async () => {
    const other: Series = { label: "Queue", points: hourly([1, 2, 3, 4]) };
    const { rerender } = render(<LineChart {...COMMON} series={[LATENCY]} />);
    expect(screen.queryByRole("list", { name: "Legend" })).toBeNull();
    rerender(<LineChart {...COMMON} series={[LATENCY, other]} />);
    expect(within(screen.getByRole("list", { name: "Legend" })).getAllByRole("listitem")).toHaveLength(2);
    focusPlot();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("status").textContent).toMatch(/^Queue, .*, 1 ms$/);
  });

  it("toggles to a table with the same data and back", async () => {
    render(<LineChart {...COMMON} series={[{ label: "Latency", points: hourly([20, null]) }]} />);
    await userEvent.click(screen.getByRole("button", { name: "View as table" }));
    const table = screen.getByRole("table", { name: "Response time, as a table" });
    expect(within(table).getByRole("columnheader", { name: /Latency \(ms\)/ })).toBeTruthy();
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("No data")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "View as chart" }));
    expect(screen.getByRole("application")).toBeTruthy();
  });

  it("renders 1 000 points quickly and keeps the drawing small", () => {
    const many = Array.from({ length: 1000 }, (_, i) => ({
      t: START + i * 60_000,
      value: 50 + 20 * Math.sin(i / 20),
    }));
    const started = performance.now();
    const { container } = render(<LineChart {...COMMON} series={[{ label: "Latency", points: many }]} />);
    expect(performance.now() - started).toBeLessThan(50);
    expect(container.querySelectorAll("circle, rect, polygon").length).toBeLessThan(10);
    const path = container.querySelector(".ui-chart__line")?.getAttribute("d") ?? "";
    expect(path.split("L").length).toBeLessThanOrEqual(400);
  });

  it("keeps the full data in the table view", async () => {
    const many = Array.from({ length: 1000 }, (_, i) => ({ t: START + i * 60_000, value: i }));
    render(<LineChart {...COMMON} series={[{ label: "Latency", points: many }]} />);
    await userEvent.click(screen.getByRole("button", { name: "View as table" }));
    expect(screen.getAllByRole("row")).toHaveLength(1001);
  });
});

describe("AreaChart", () => {
  it("fills under the line and includes zero on the value axis", () => {
    const { container } = render(<AreaChart {...COMMON} series={[LATENCY]} />);
    expect(container.querySelector(".ui-chart__area")?.getAttribute("d")).toMatch(/Z$/);
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });
});

describe("BarChart", () => {
  const days: Series = { label: "Messages", points: hourly([10, 0, null, 7]) };

  it("reads each bar and says no data for a missing one", async () => {
    render(<BarChart {...COMMON} unit="messages" series={[days]} />);
    focusPlot();
    const status = screen.getByRole("status");
    expect(status.textContent).toMatch(/10 messages$/);
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    expect(status.textContent).toMatch(/no data$/);
  });

  it("draws one bar per measured value", () => {
    const { container } = render(<BarChart {...COMMON} series={[days]} />);
    expect(container.querySelectorAll(".ui-chart__bar")).toHaveLength(3);
  });

  it("has a table view", async () => {
    render(<BarChart {...COMMON} series={[days]} stacked />);
    await userEvent.click(screen.getByRole("button", { name: "View as table" }));
    expect(screen.getByRole("table", { name: "Response time, as a table" })).toBeTruthy();
  });

  it("shows an empty state", () => {
    render(<BarChart {...COMMON} series={[]} />);
    expect(screen.getByText("No data for this period")).toBeTruthy();
  });
});

describe("HeatGrid", () => {
  const props = {
    title: "Activity",
    period: "Last 7 days",
    rows: ["Mon", "Tue"],
    columns: ["09", "10", "11"],
    values: [
      [1, 4, null],
      [0, 2, 8],
    ],
    unit: "messages",
  };

  it("moves in two dimensions and announces the cell", async () => {
    render(<HeatGrid {...props} />);
    focusPlot();
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Mon, 09, 1 messages");
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    expect(status.textContent).toBe("Mon, 11, no data");
    await userEvent.keyboard("{ArrowDown}");
    expect(status.textContent).toBe("Tue, 11, 8 messages");
  });

  it("marks gaps differently from zero", () => {
    const { container } = render(<HeatGrid {...props} />);
    expect(container.querySelectorAll(".ui-chart__cell--gap")).toHaveLength(1);
  });

  it("has a table view and an empty state", async () => {
    const { rerender } = render(<HeatGrid {...props} />);
    await userEvent.click(screen.getByRole("button", { name: "View as table" }));
    expect(screen.getByRole("table", { name: "Activity, as a table" })).toBeTruthy();
    rerender(<HeatGrid {...props} values={[[null], [null]]} columns={["09"]} />);
    expect(screen.getByText("No data for this period")).toBeTruthy();
  });
});

describe("Meter", () => {
  it("exposes value, limit and level with an icon-and-word status", () => {
    render(<Meter label="Disk space" value={420} max={500} unit="GB" warnAt={400} dangerAt={475} />);
    const meter = screen.getByRole("meter", { name: "Disk space" });
    expect(meter.getAttribute("aria-valuenow")).toBe("420");
    expect(meter.getAttribute("aria-valuetext")).toBe("420 GB of 500 GB (84%). Getting full.");
    expect(screen.getByText("Getting full")).toBeTruthy();
  });

  it("reaches the danger level", () => {
    render(<Meter label="Disk space" value={490} max={500} unit="GB" warnAt={400} dangerAt={475} />);
    expect(screen.getByText("At or near the limit")).toBeTruthy();
  });

  it("shows not measured instead of zero", () => {
    render(<Meter label="Disk space" value={null} max={500} unit="GB" />);
    expect(screen.getAllByText("Not measured").length).toBeGreaterThan(0);
    expect(screen.getByRole("meter").hasAttribute("aria-valuenow")).toBe(false);
  });
});

describe("Sparkline", () => {
  it("summarises the trend for screen readers", () => {
    render(<Sparkline label="Sessions" unit="sessions" points={hourly([4, 9, 6])} />);
    expect(
      screen.getByRole("img", {
        name: "Sessions trend: latest 6 sessions, lowest 4 sessions, highest 9 sessions",
      }),
    ).toBeTruthy();
  });

  it("says no data when empty or all gaps", () => {
    render(<Sparkline label="Sessions" points={hourly([null])} />);
    expect(screen.getByRole("img", { name: "Sessions trend: no data" })).toBeTruthy();
  });

  it("breaks at gaps", () => {
    const { container } = render(<Sparkline label="Sessions" points={hourly([1, 2, null, 3, 4])} />);
    expect(container.querySelector("path")?.getAttribute("d")?.match(/M/g)).toHaveLength(2);
  });
});
