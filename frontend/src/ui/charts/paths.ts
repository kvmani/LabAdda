import type { ChartPoint } from "./types";

type Mapper = (value: number) => number;

/** Split a series into runs of measured points; a null ends the run, so gaps stay gaps. */
export function runs(points: ChartPoint[]): ChartPoint[][] {
  const result: ChartPoint[][] = [];
  let current: ChartPoint[] = [];
  for (const point of points) {
    if (point.value === null) {
      if (current.length > 0) result.push(current);
      current = [];
    } else {
      current.push(point);
    }
  }
  if (current.length > 0) result.push(current);
  return result;
}

function coordinate(point: ChartPoint, x: Mapper, y: Mapper): string {
  return `${x(point.t).toFixed(1)} ${y(point.value ?? 0).toFixed(1)}`;
}

/** SVG path for a line; runs of one point have no line (they are drawn as a mark). */
export function linePath(points: ChartPoint[], x: Mapper, y: Mapper): string {
  return runs(points)
    .filter((run) => run.length > 1)
    .map((run) => "M" + run.map((point) => coordinate(point, x, y)).join(" L"))
    .join(" ");
}

/** SVG path for the filled area under each run, closed down to `baseline`. */
export function areaPath(points: ChartPoint[], x: Mapper, y: Mapper, baseline: number): string {
  return runs(points)
    .filter((run) => run.length > 1)
    .map((run) => {
      const first = run[0];
      const last = run[run.length - 1];
      if (!first || !last) return "";
      const edge = (point: ChartPoint) => `${x(point.t).toFixed(1)} ${baseline.toFixed(1)}`;
      return `M${edge(first)} L${run.map((point) => coordinate(point, x, y)).join(" L")} L${edge(last)} Z`;
    })
    .join(" ");
}

/** Index of the point whose time is closest to `t`. */
export function nearestIndex(points: ChartPoint[], t: number): number {
  let best = 0;
  points.forEach((point, index) => {
    if (Math.abs(point.t - t) < Math.abs((points[best]?.t ?? 0) - t)) best = index;
  });
  return best;
}
