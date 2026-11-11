import { DASHES, Mark } from "./marks";
import { areaPath, linePath, runs } from "./paths";
import { extent, linearScale, niceTicks, timeTicks, type NiceTicks, type Scale } from "./scale";
import type { ChartPoint } from "./types";
import type { Active } from "./useActivePoint";
import { ValueAxis } from "./ValueAxis";

export const MARGIN = { top: 26, right: 12, bottom: 28, left: 48 };
const MARK_LIMIT = 40;

type SeriesLayerProps = {
  index: number;
  points: ChartPoint[];
  area: boolean;
  marked: boolean;
  x: Scale;
  y: Scale;
  baseline: number;
};

function SeriesLayer({ index, points, area, marked, x, y, baseline }: SeriesLayerProps) {
  return (
    <g className={`ui-chart__s${index}`}>
      {area && <path className="ui-chart__area" d={areaPath(points, x, y, baseline)} />}
      <path className="ui-chart__line" d={linePath(points, x, y)} strokeDasharray={DASHES[index]} />
      {runs(points).flatMap((run) =>
        run.length === 1 || marked
          ? run.map((p) => (
              <Mark
                key={p.t}
                className="ui-chart__mark"
                shape={index}
                x={x(p.t)}
                y={y(p.value ?? 0)}
                size={3}
              />
            ))
          : [],
      )}
    </g>
  );
}

type TimeDrawingProps = {
  width: number;
  height: number;
  drawn: ChartPoint[][];
  area: boolean;
  axis: NiceTicks;
  times: [number, number] | undefined;
  unit?: string;
  formatTime: (t: number) => string;
  formatValue: (value: number) => string;
  active: Active | null;
};

/** The SVG contents of a line or area chart: axes, series, gaps and the point being read. */
export function TimeDrawing({ width, height, drawn, area, axis, times, active, ...text }: TimeDrawingProps) {
  const [t0, t1] = times ?? [0, 1];
  const right = width - MARGIN.right;
  const x = linearScale([t0, t1], [MARGIN.left, right]);
  const y = linearScale([axis.min, axis.max], [height - MARGIN.bottom, MARGIN.top]);
  const marked = drawn.reduce((sum, points) => sum + points.length, 0) <= MARK_LIMIT;
  const point = active ? drawn[active.series]?.[active.index] : undefined;
  return (
    <>
      <ValueAxis
        ticks={axis.ticks}
        y={y}
        left={MARGIN.left}
        right={right}
        unit={text.unit}
        format={text.formatValue}
      />
      {timeTicks(t0, t1, width < 480 ? 3 : 6).map((tick) => (
        <text key={tick} className="ui-chart__tick" x={x(tick)} y={height - 8} textAnchor="middle">
          {text.formatTime(tick)}
        </text>
      ))}
      {drawn.map((points, index) => (
        <SeriesLayer key={index} {...{ index, points, area, marked, x, y }} baseline={y(axis.min)} />
      ))}
      {active && point && point.value !== null && (
        <g className={`ui-chart__s${active.series}`}>
          <line
            className="ui-chart__guide"
            x1={x(point.t)}
            x2={x(point.t)}
            y1={MARGIN.top}
            y2={height - MARGIN.bottom}
          />
          <Mark
            className="ui-chart__active"
            shape={active.series}
            x={x(point.t)}
            y={y(point.value)}
            size={6}
          />
        </g>
      )}
    </>
  );
}

/** Time extent and a value axis; area charts always include zero. */
export function timeAxis(drawn: ChartPoint[][], area: boolean) {
  const times = extent(drawn.flatMap((points) => points.map((point) => point.t)));
  const values = extent(drawn.flatMap((points) => points.map((point) => point.value ?? NaN)));
  const [low, high] = values ?? [0, 1];
  return { times, axis: niceTicks(area ? Math.min(0, low) : low, high, 5) };
}
