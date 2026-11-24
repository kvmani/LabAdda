import type { ChartPoint, Series, Tone } from "../../ui";
import type { FeatureMomentum, PerfPoint, Span, Trend, Trends } from "./types";

export const HORIZONS = [
  { value: "8", label: "Last 8 weeks" },
  { value: "12", label: "Last 12 weeks" },
  { value: "26", label: "Last 6 months" },
  { value: "52", label: "Last 12 months" },
];

export const SPANS: { value: Span; label: string }[] = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

export function parseWeeks(value: string | null): string {
  return HORIZONS.find((option) => option.value === value)?.value ?? "12";
}

export function parseSpan(value: string | null): Span {
  return SPANS.find((option) => option.value === value)?.value ?? "7d";
}

export const TREND_WORDS: Record<Trend, { label: string; tone: Tone }> = {
  growing: { label: "Growing", tone: "ok" },
  new: { label: "New", tone: "info" },
  core: { label: "Core", tone: "ok" },
  steady: { label: "Steady", tone: "neutral" },
  declining: { label: "Declining", tone: "warn" },
  dormant: { label: "Dormant", tone: "danger" },
  unused: { label: "Unused", tone: "danger" },
  unknown: { label: "Not enough data", tone: "neutral" },
};

/** The three decisions an administrator takes from momentum: invest, look closer, retire. */
export type Bucket = "focus" | "watch" | "drop";
const BUCKET_OF: Partial<Record<Trend, Bucket>> = {
  growing: "focus",
  new: "focus",
  core: "focus",
  declining: "watch",
  dormant: "drop",
  unused: "drop",
};

export function decisions(features: FeatureMomentum[]): Record<Bucket, FeatureMomentum[]> {
  const out: Record<Bucket, FeatureMomentum[]> = { focus: [], watch: [], drop: [] };
  for (const feature of features) {
    const bucket = BUCKET_OF[feature.trend];
    if (bucket) out[bucket].push(feature);
  }
  return out;
}

const whole = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

export function formatCount(value: number | null): string {
  return value === null ? "Not measured" : whole.format(value);
}

export function formatRate(value: number | null): string {
  return value === null ? "Not measured" : `${oneDecimal.format(value * 100)} %`;
}

export function formatMs(value: number | null): string {
  return value === null ? "Not measured" : `${whole.format(value)} ms`;
}

/** A change as words with its sign; nothing to compare with is said, never shown as 0 %. */
export function formatChange(change: number | null): string {
  if (change === null) return "No earlier figure to compare";
  const percent = Math.round(change * 100);
  if (percent === 0) return "No change";
  return `${percent > 0 ? "Up" : "Down"} ${Math.abs(percent)} %`;
}

/** The relative change between two figures, or null when either is missing or the base is 0. */
export function relative(current: number | null, previous: number | null): number | null {
  if (current === null || previous === null || previous === 0) return null;
  return (current - previous) / previous;
}

function weekTime(start: string): number {
  return Date.parse(`${start}T00:00:00Z`);
}

/** Complete weeks only: a week still running would look like a sudden fall in use. */
function complete(trends: Trends) {
  return trends.points.flatMap((point, index) => (point.partial ? [] : [{ point, index }]));
}

/** Weekly series for the busiest features (the chart draws at most four lines). */
export function featureSeries(trends: Trends, limit = 4): Series[] {
  const ranked = [...trends.features]
    .filter((feature) => (feature.share ?? 0) > 0)
    .sort((left, right) => (right.share ?? 0) - (left.share ?? 0))
    .slice(0, limit);
  return ranked.map((feature) => ({
    label: feature.label,
    points: complete(trends).map(({ point }) => ({
      t: weekTime(point.start),
      value: point.values ? (point.values[feature.key] ?? 0) : null,
    })),
  }));
}

export function peopleSeries(trends: Trends): Series[] {
  return [
    {
      label: "Active people",
      points: complete(trends).map(({ point }) => ({ t: weekTime(point.start), value: point.active_people })),
    },
  ];
}

export function sparkPoints(trends: Trends, feature: FeatureMomentum): ChartPoint[] {
  return complete(trends).map(({ point, index }) => ({
    t: weekTime(point.start),
    value: feature.sparkline[index] ?? null,
  }));
}

function series(points: PerfPoint[], label: string, read: (point: PerfPoint) => number | null): Series {
  return { label, points: points.map((point) => ({ t: Date.parse(point.start), value: read(point) })) };
}

export function latencySeries(points: PerfPoint[]): Series[] {
  return [
    series(points, "Slowest 5 % (p95)", (point) => point.p95_ms),
    series(points, "Median (p50)", (point) => point.p50_ms),
  ];
}

export function errorSeries(points: PerfPoint[]): Series[] {
  return [
    series(points, "Server errors", (point) => (point.error_rate === null ? null : point.error_rate * 100)),
  ];
}

export function trafficSeries(points: PerfPoint[]): Series[] {
  return [series(points, "Requests", (point) => point.requests)];
}
