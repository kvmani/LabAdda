import type { Series } from "./types";

const DAY = 86_400_000;

/** Default time text: date and time for short spans, date only for long ones. */
export function makeTimeFormatter(series: Series[]): (t: number) => string {
  let low = Infinity;
  let high = -Infinity;
  for (const item of series) {
    for (const point of item.points) {
      low = Math.min(low, point.t);
      high = Math.max(high, point.t);
    }
  }
  const short = high - low <= 2 * DAY;
  const options: Intl.DateTimeFormatOptions = short
    ? { hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "short" };
  const formatter = new Intl.DateTimeFormat(undefined, options);
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
