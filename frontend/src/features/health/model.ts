import { fmtBytes } from "../../format";
import type { ChartPoint, HealthStatus } from "../../ui";
import type { HealthItem } from "./types";

/** An item whose last check is older than four sampling intervals is shown as stale (UX-10). */
export const STALE_INTERVALS = 4;

export function effectiveStatus(item: HealthItem, ageSeconds: number, interval: number): HealthStatus {
  if (item.status === "unsupported") return item.status;
  return ageSeconds > interval * STALE_INTERVALS ? "stale" : item.status;
}

export function formatAge(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 90) return `${whole} s ago`;
  if (whole < 5400) return `${Math.round(whole / 60)} min ago`;
  return `${Math.round(whole / 3600)} h ago`;
}

function duration(seconds: number): string {
  if (seconds < 120) return `${Math.round(seconds)} s`;
  if (seconds < 7200) return `${Math.round(seconds / 60)} min`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} days`;
}

/** The headline figure with its unit, or an honest "Not measured" (AD-03). */
export function formatValue(value: number | string | null, unit: string): string {
  if (value === null) return "Not measured";
  if (typeof value === "string") return value;
  if (unit === "bytes") return fmtBytes(value);
  if (unit === "seconds") return duration(value);
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`.trim();
}

export function overallSentence(overall: HealthStatus, problems: number): string {
  switch (overall) {
    case "healthy":
      return "Everything that can be checked is working.";
    case "degraded":
      return `${problems} ${problems === 1 ? "check needs" : "checks need"} attention.`;
    case "unavailable":
      return `${problems} ${problems === 1 ? "check has" : "checks have"} failed. Something is not working.`;
    case "stale":
      return "Some figures are out of date.";
    case "unsupported":
    case "unknown":
      return "Some checks have no figures yet, so the system is not confirmed healthy.";
  }
}

const SCALES: [string, number][] = [
  ["B", 1],
  ["KiB", 1024],
  ["MiB", 1024 ** 2],
  ["GiB", 1024 ** 3],
  ["TiB", 1024 ** 4],
];

/** Chart values for a unit: bytes are rescaled so axis numbers stay short. */
export function scaleValues(values: number[], unit: string): { factor: number; unit: string } {
  if (unit !== "bytes") return { factor: 1, unit };
  const largest = Math.max(0, ...values);
  const [name, size] = [...SCALES].reverse().find(([, size]) => largest >= size) ?? SCALES[0]!;
  return { factor: 1 / size, unit: name };
}

const GAP_MS = 3 * 60_000;

/** Stored minutes become points; a hole longer than a few minutes is drawn as a gap, not a line. */
export function chartPoints(rows: { bucket_start: string; value: number }[], factor: number): ChartPoint[] {
  const points: ChartPoint[] = [];
  for (const row of rows) {
    const t = Date.parse(row.bucket_start);
    const last = points[points.length - 1];
    if (last && t - last.t > GAP_MS) points.push({ t: last.t + 60_000, value: null });
    points.push({ t, value: row.value * factor });
  }
  return points;
}
