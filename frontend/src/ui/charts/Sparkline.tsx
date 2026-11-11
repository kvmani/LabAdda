import { downsample } from "./downsample";
import { defaultValueFormat, withUnit } from "./format";
import { linePath, runs } from "./paths";
import { extent, linearScale } from "./scale";
import type { ChartPoint } from "./types";
import "./charts.css";

type SparklineProps = {
  /** What the trend measures, for example "Sessions". Read out with the summary. */
  label: string;
  points: ChartPoint[];
  unit?: string;
  formatValue?: (value: number) => string;
};

const WIDTH = 120;
const HEIGHT = 32;
const PAD = 3;

/** A small trend line with no axes, for inside a StatTile. The exact numbers sit beside it. */
export function Sparkline({ label, points, unit, formatValue = defaultValueFormat }: SparklineProps) {
  const drawn = downsample(points, 120);
  const t = extent(drawn.map((point) => point.t));
  const v = extent(drawn.map((point) => point.value ?? NaN));
  const latest = [...points].reverse().find((point) => point.value !== null)?.value ?? null;
  const show = (value: number) => withUnit(value, unit, formatValue);
  const summary =
    v && latest !== null
      ? `${label} trend: latest ${show(latest)}, lowest ${show(v[0])}, highest ${show(v[1])}`
      : `${label} trend: no data`;
  if (!t || !v) {
    return (
      <svg className="ui-sparkline" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={summary} />
    );
  }
  const x = linearScale(t, [PAD, WIDTH - PAD]);
  const y = linearScale(v, [HEIGHT - PAD, PAD]);
  const lastRun = runs(drawn).pop();
  const end = lastRun?.[lastRun.length - 1];
  return (
    <svg
      className="ui-sparkline ui-chart__s0"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={summary}
    >
      <path className="ui-chart__line" d={linePath(drawn, x, y)} />
      {end && <circle className="ui-chart__mark" cx={x(end.t)} cy={y(end.value ?? 0)} r={2.5} />}
      {runs(drawn)
        .filter((run) => run.length === 1)
        .map((run) => (
          <circle
            key={run[0]?.t}
            className="ui-chart__mark"
            cx={x(run[0]?.t ?? 0)}
            cy={y(run[0]?.value ?? 0)}
            r={2}
          />
        ))}
    </svg>
  );
}
