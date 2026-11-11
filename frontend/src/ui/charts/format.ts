import type { Series } from "./types";

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

/** Pick the shortest time text that is still unambiguous for this data's span and spacing. */
export function timeFormatOptions(span: number, minGap: number): Intl.DateTimeFormatOptions {
  if (minGap >= 20 * HOUR) {
    return span <= 14 * DAY ? { weekday: "short", day: "numeric" } : { day: "numeric", month: "short" };
  }
  if (span <= DAY) return { hour: "2-digit", minute: "2-digit" };
  if (span <= 7 * DAY) return { weekday: "short", hour: "2-digit", minute: "2-digit" };
  return { day: "numeric", month: "short" };
}

/** Default time text for axis labels, adapted to the data. */
export function makeTimeFormatter(series: Series[]): (t: number) => string {
  const times = [...new Set(series.flatMap((item) => item.points.map((point) => point.t)))].sort(
    (a, b) => a - b,
  );
  let minGap = Infinity;
  for (let index = 1; index < times.length; index += 1) {
    minGap = Math.min(minGap, (times[index] ?? 0) - (times[index - 1] ?? 0));
  }
  const span = (times[times.length - 1] ?? 0) - (times[0] ?? 0);
  const formatter = new Intl.DateTimeFormat(undefined, timeFormatOptions(span, minGap));
  return (t) => formatter.format(new Date(t));
}

const fullTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** Unambiguous time for announcements and tables. */
export function formatFullTime(t: number): string {
  return fullTime.format(new Date(t));
}

export function defaultValueFormat(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/** "42 ms", or "no data" for a gap. */
export function withUnit(
  value: number | null,
  unit: string | undefined,
  format: (v: number) => string,
): string {
  if (value === null) return "no data";
  return unit ? `${format(value)} ${unit}` : format(value);
}

/** True when no series has a measured value. */
export function hasNoData(series: Series[]): boolean {
  return series.every((item) => item.points.every((point) => point.value === null));
}
