import { fmtBytes } from "../../format";
import type { ChartPoint, HealthStatus } from "../../ui";
import { SUPPRESSED_TEXT, dayTime } from "../activity/model";
import { formatAge } from "../health/model";
import type { DayPoint, OverviewTile, Severity } from "./types";

export const POLL_MS = 15_000;
/** Figures not refreshed for four polls are shown as stale (UX-10). */
export const STALE_AFTER_SECONDS = (POLL_MS / 1000) * 4;

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Urgent",
  error: "Problem",
  warning: "Warning",
  info: "To confirm",
};

const PERIOD: Record<string, string> = {
  active_today: "Today",
  signed_in_now: "Seen in the last 5 minutes",
  connected_now: "Right now",
  storage_used: "Files and database, now",
  last_backup: "Latest verified or failed run",
  open_events: "Not yet acknowledged",
};

function span(seconds: number): string {
  if (seconds < 120) return `${Math.round(seconds)} seconds`;
  if (seconds < 7200) return `${Math.round(seconds / 60)} minutes`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} hours`;
  return `${Math.round(seconds / 86400)} days`;
}

/** The figure in words with its unit; a missing or hidden figure says so and is never 0. */
export function tileValue(tile: OverviewTile): string {
  if (tile.state === "suppressed") return SUPPRESSED_TEXT;
  if (tile.value === null) return "Not measured";
  const count = (unit: string) => `${tile.value?.toLocaleString()} ${unit}`;
  switch (tile.unit) {
    case "bytes":
      return fmtBytes(tile.value);
    case "seconds":
      return `${span(tile.value)} ago`;
    case "people":
      return count(tile.value === 1 ? "person" : "people");
    case "connections":
      return count(tile.value === 1 ? "connection" : "connections");
    case "events":
      return count(tile.value === 1 ? "event" : "events");
  }
}

/** A status word to show beside the figure, or none for an ordinary measurement. */
export function tileStatus(tile: OverviewTile): HealthStatus | undefined {
  if (tile.state === "measured" || tile.state === "suppressed") return undefined;
  return tile.state;
}

export function tileNote(tile: OverviewTile, now: number): string {
  const parts = [PERIOD[tile.key] ?? ""];
  if (tile.state === "suppressed") parts.push("Hidden below 5 people so no one can be picked out");
  if (tile.updated_at) parts.push(`Updated ${formatAge((now - Date.parse(tile.updated_at)) / 1000)}`);
  return parts.filter(Boolean).join(". ");
}

/** Seven daily values as chart points, oldest first, null where the day was not measured. */
export function trendPoints(values: (number | null)[], firstDay: string): ChartPoint[] {
  const start = dayTime(firstDay);
  return values.map((value, index) => ({ t: start + index * 86_400_000, value }));
}

export function dayPoints(points: DayPoint[]): ChartPoint[] {
  return points.map((point) => ({ t: dayTime(point.day), value: point.value }));
}

export function overallSentence(overall: HealthStatus, count: number): string {
  if (count === 0 && overall === "healthy") return "Nothing needs attention.";
  if (count === 0) return "No problems were found, but some checks have no figures yet.";
  return `${count} ${count === 1 ? "thing needs" : "things need"} attention.`;
}
