import type { ChartPoint, Series } from "../../ui";
import { scaleValues } from "../health/model";
import type { DayRange, FeaturePoint, Figure, Period, SummaryCharts, Tile } from "./types";

export const PERIODS: { value: Period; label: string }[] = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "12m", label: "Last 12 months" },
];

export function parsePeriod(value: string | null): Period {
  return PERIODS.find((option) => option.value === value)?.value ?? "30d";
}

export function periodLabel(period: Period): string {
  return PERIODS.find((option) => option.value === period)?.label ?? "";
}

/** Site-local calendar days are drawn at UTC midnight and always formatted in UTC. */
export function dayTime(day: string): number {
  return Date.parse(`${day}T00:00:00Z`);
}

const dayFormat = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const monthFormat = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric", timeZone: "UTC" });

export function formatDay(t: number): string {
  return dayFormat.format(new Date(t));
}

export function rangeText(range: DayRange): string {
  return `${formatDay(dayTime(range.first_day))} to ${formatDay(dayTime(range.last_day))}`;
}

const count = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 0 });
const percent = (value: number) =>
  value.toLocaleString(undefined, { style: "percent", maximumFractionDigits: 0 });

export function tileValue(tile: Tile): string {
  if (tile.value === null) return "Not measured";
  return tile.unit === "fraction" ? percent(tile.value) : count(tile.value);
}

/** "Up 3 from 12 in the previous period", in words, never a bare arrow. */
export function comparison(tile: Tile): string {
  if (tile.value === null) return "No figures were collected in this period.";
  if (tile.previous === null) return "No figures for the previous period.";
  const format = tile.unit === "fraction" ? percent : count;
  const change = tile.value - tile.previous;
  if (Math.abs(change) < 1e-9) return `Same as the previous period (${format(tile.previous)}).`;
  const direction = change > 0 ? "Up" : "Down";
  return `${direction} ${format(Math.abs(change))} from ${format(tile.previous)} in the previous period.`;
}

export const SUPPRESSED_TEXT = "Fewer than 5";

export function figureText(figure: Figure | null): string {
  if (figure === null) return "Not applicable";
  if (figure.state === "suppressed") return SUPPRESSED_TEXT;
  if (figure.state === "unknown") return "Not measured";
  return count(figure.value);
}

/** Sort key for a figure column: suppressed and missing figures sort below every number. */
export function figureSort(figure: Figure | null): number {
  return figure?.state === "shown" ? figure.value : -1;
}

export function activeSeries(charts: SummaryCharts): Series[] {
  const points: ChartPoint[] = charts.active_per_day.map((point) => ({
    t: dayTime(point.day),
    value: point.value,
  }));
  return [{ label: "Active people", points }];
}

// Seven features in four stacks: a stacked chart reads well with at most four series (UX-09).
const FEATURE_GROUPS: { label: string; keys: string[] }[] = [
  { label: "Noticeboard", keys: ["posts.created", "replies.created"] },
  { label: "Chat", keys: ["chat.messages"] },
  { label: "Tasks", keys: ["tasks.created", "tasks.completed"] },
  { label: "Files added", keys: ["uploads.count"] },
];

function groupValue(point: FeaturePoint, keys: string[]): number | null {
  if (point.values === null) return null;
  const values = point.values;
  return keys.reduce((total, key) => total + (values[key] ?? 0), 0);
}

export function featureSeries(charts: SummaryCharts): Series[] {
  return FEATURE_GROUPS.map((group) => ({
    label: group.label,
    points: charts.features.points.map((point) => ({
      t: dayTime(point.start),
      value: groupValue(point, group.keys),
    })),
  }));
}

export function bucketFormatter(bucket: SummaryCharts["features"]["bucket"]): (t: number) => string {
  if (bucket === "month") return (t) => monthFormat.format(new Date(t));
  if (bucket === "week") return (t) => `Week of ${formatDay(t)}`;
  return formatDay;
}

/** Totals of every feature over the period, including those grouped together in the chart. */
export function featureTotals(charts: SummaryCharts): { label: string; value: number | null }[] {
  const measured = charts.features.points.filter((point) => point.values !== null);
  return charts.features.series.map((series) => ({
    label: series.label,
    value: measured.length
      ? measured.reduce((total, point) => total + (point.values?.[series.key] ?? 0), 0)
      : null,
  }));
}

// Short names: the heat grid gives row labels a narrow column.
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const HOURS = Array.from({ length: 24 }, (_, hour) => `${String(hour).padStart(2, "0")}:00`);

export function heatValues(charts: SummaryCharts): (number | null)[][] {
  const grid: (number | null)[][] = WEEKDAYS.map(() => HOURS.map(() => null));
  for (const cell of charts.weekday_hour.cells) {
    const row = grid[cell.weekday - 1];
    if (row) row[cell.hour] = cell.value;
  }
  return grid;
}

export function storageSeries(charts: SummaryCharts): { unit: string; series: Series[] } {
  const values = charts.storage.flatMap((point) => [point.files_bytes ?? 0, point.database_bytes ?? 0]);
  const { factor, unit } = scaleValues(values, "bytes");
  const line = (label: string, pick: (point: SummaryCharts["storage"][number]) => number | null) => ({
    label,
    points: charts.storage.map((point) => {
      const value = pick(point);
      return { t: dayTime(point.day), value: value === null ? null : value * factor };
    }),
  });
  return {
    unit,
    series: [line("Files", (point) => point.files_bytes), line("Database", (point) => point.database_bytes)],
  };
}

/** Named categories (units, size bands) drawn as bars: each bar's time is its position. */
export function categorySeries(label: string, bars: { label: string; value: number }[]): Series[] {
  return [{ label, points: bars.map((bar, index) => ({ t: index, value: bar.value })) }];
}

export function categoryFormatter(bars: { label: string }[]): (t: number) => string {
  return (t) => bars[t]?.label ?? "";
}
