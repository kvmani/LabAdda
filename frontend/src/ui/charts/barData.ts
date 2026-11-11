import { useMemo } from "react";
import { extent, niceTicks, type NiceTicks } from "./scale";
import type { Series } from "./types";

export type BarData = {
  categories: number[];
  /** Value of series `s` in category `c`, or null for a gap. */
  valueAt: (s: number, c: number) => number | null;
  axis: NiceTicks;
};

/** Categories (every distinct time), lookups and a value axis that starts at zero. */
export function useBarData(series: Series[], stacked: boolean): BarData {
  return useMemo(() => {
    const categories = [...new Set(series.flatMap((item) => item.points.map((p) => p.t)))].sort(
      (a, b) => a - b,
    );
    const lookups = series.map((item) => new Map(item.points.map((p) => [p.t, p.value])));
    const valueAt = (s: number, c: number) => lookups[s]?.get(categories[c] ?? 0) ?? null;
    const measured = categories.map((_, c) => series.map((_s, s) => valueAt(s, c) ?? 0));
    const values = stacked ? measured.map((row) => row.reduce((sum, v) => sum + v, 0)) : measured.flat();
    const [low, high] = extent([0, ...values]) ?? [0, 1];
    return { categories, valueAt, axis: niceTicks(low, high, 5) };
  }, [series, stacked]);
}
