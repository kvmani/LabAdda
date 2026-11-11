/** One sample. `value` is null where nothing was measured; charts draw that as a gap. */
export type ChartPoint = { t: number; value: number | null };

/** A named run of samples in time order. `t` is epoch milliseconds. */
export type Series = { label: string; points: ChartPoint[] };

/** Props every chart shares (UX-09). */
export type ChartBaseProps = {
  /** Names the chart for everyone, including screen readers. */
  title: string;
  series: Series[];
  /** Unit of the values, for example "ms" or "GB"; shown on the axis and in announcements. */
  unit?: string;
  /** The span the data covers, for example "Last 24 hours". */
  period: string;
  /** When the data was last refreshed, for example "Updated 12 s ago". Shown as unknown if absent. */
  updated?: string;
  /** Text for a time value; the default adapts to the span of the data. */
  formatTime?: (t: number) => string;
  /** Text for a value, without its unit. */
  formatValue?: (value: number) => string;
  /** Drawing height in pixels; the width follows the container. */
  height?: number;
};
