import { useMemo } from "react";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { downsample } from "./downsample";
import { defaultValueFormat, formatFullTime, hasNoData, makeTimeFormatter, withUnit } from "./format";
import { DASHES, Mark } from "./marks";
import { areaPath, linePath, runs } from "./paths";
import { extent, linearScale, niceTicks, timeTicks } from "./scale";
import { SeriesTable } from "./SeriesTable";
import type { ChartBaseProps } from "./types";
import { useActivePoint } from "./useActivePoint";
import { ValueAxis } from "./ValueAxis";

type TimeChartProps = ChartBaseProps & { area: boolean };

const MARGIN = { top: 18, right: 12, bottom: 28, left: 48 };
const MARK_LIMIT = 40;
const MAX_SERIES = 4;

/** Line and area charts share everything but the fill, so one component draws both. */
export function TimeChart({ area, height = 240, ...props }: TimeChartProps) {
  const { title, unit, period, updated } = props;
  const series = useMemo(() => props.series.slice(0, MAX_SERIES), [props.series]);
  const drawn = useMemo(() => series.map((item) => downsample(item.points)), [series]);
  const { active, setActive, handlers } = useActivePoint(drawn.map((points) => points.length));
  const formatTime = props.formatTime ?? makeTimeFormatter(series);
  const formatValue = props.formatValue ?? defaultValueFormat;

  const times = extent(drawn.flatMap((points) => points.map((point) => point.t)));
  const values = extent(drawn.flatMap((points) => points.map((point) => point.value ?? NaN)));
  const [valueLow, valueHigh] = values ?? [0, 1];
  const axis = niceTicks(area ? Math.min(0, valueLow) : valueLow, valueHigh, 5);

  const point = active ? drawn[active.series]?.[active.index] : undefined;
  const readout =
    active && point
      ? `${series[active.series]?.label ?? ""}, ${formatFullTime(point.t)}, ${withUnit(point.value, unit, formatValue)}`
      : null;

  function pointer(x: number | null, width: number) {
    if (x === null || !times) {
      setActive(null);
      return;
    }
    const t = linearScale([MARGIN.left, width - MARGIN.right], times).invert(x);
    const row = active?.series ?? 0;
    const points = drawn[row] ?? [];
    let best = 0;
    points.forEach((candidate, index) => {
      if (Math.abs(candidate.t - t) < Math.abs((points[best]?.t ?? 0) - t)) best = index;
    });
    setActive({ series: row, index: best });
  }

  return (
    <ChartFrame
      title={title}
      period={period}
      updated={updated}
      legend={series.map((item) => item.label)}
      empty={series.length === 0 || hasNoData(series)}
      table={
        <SeriesTable
          title={title}
          series={series}
          unit={unit}
          formatValue={formatValue}
          formatTime={props.formatTime}
        />
      }
    >
      <ChartPlot
        label={`${title}, ${period}`}
        height={height}
        readout={readout}
        handlers={handlers}
        onPointer={pointer}
      >
        {(width) => {
          const [t0, t1] = times ?? [0, 1];
          const x = linearScale([t0, t1], [MARGIN.left, width - MARGIN.right]);
          const y = linearScale([axis.min, axis.max], [height - MARGIN.bottom, MARGIN.top]);
          const marked = drawn.reduce((sum, points) => sum + points.length, 0) <= MARK_LIMIT;
          return (
            <>
              <ValueAxis
                ticks={axis.ticks}
                y={y}
                left={MARGIN.left}
                right={width - MARGIN.right}
                unit={unit}
                format={formatValue}
              />
              {timeTicks(t0, t1, width < 480 ? 3 : 6).map((tick) => (
                <text key={tick} className="ui-chart__tick" x={x(tick)} y={height - 8} textAnchor="middle">
                  {formatTime(tick)}
                </text>
              ))}
              {drawn.map((points, index) => (
                <g key={series[index]?.label} className={`ui-chart__s${index}`}>
                  {area && <path className="ui-chart__area" d={areaPath(points, x, y, y(axis.min))} />}
                  <path
                    className="ui-chart__line"
                    d={linePath(points, x, y)}
                    strokeDasharray={DASHES[index]}
                  />
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
        }}
      </ChartPlot>
    </ChartFrame>
  );
}
