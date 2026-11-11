import type { ChartPoint } from "./types";

/**
 * Reduce a long series to about `limit` points without hiding peaks, dips or gaps: each bucket
 * keeps its lowest and highest real sample, and one null if the bucket contained a gap.
 */
export function downsample(points: ChartPoint[], limit = 400): ChartPoint[] {
  if (points.length <= limit) return points;
  const buckets = Math.max(1, Math.floor(limit / 2));
  const size = points.length / buckets;
  const result: ChartPoint[] = [];
  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const slice = points.slice(Math.floor(bucket * size), Math.floor((bucket + 1) * size));
    let low: ChartPoint | undefined;
    let high: ChartPoint | undefined;
    let gap: ChartPoint | undefined;
    for (const point of slice) {
      if (point.value === null) {
        gap ??= point;
        continue;
      }
      if (!low || point.value < (low.value ?? Infinity)) low = point;
      if (!high || point.value > (high.value ?? -Infinity)) high = point;
    }
    const kept = new Set([low, high, gap].filter((point): point is ChartPoint => point !== undefined));
    result.push(...[...kept].sort((a, b) => a.t - b.t));
  }
  return result;
}
