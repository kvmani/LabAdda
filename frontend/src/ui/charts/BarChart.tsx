import { useId, useMemo } from "react";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { defaultValueFormat, formatFullTime, hasNoData, makeTimeFormatter, withUnit } from "./format";
import { extent, linearScale, niceTicks } from "./scale";
import { SeriesTable } from "./SeriesTable";
import type { ChartBaseProps } from "./types";
import { useActivePoint } from "./useActivePoint";
import { ValueAxis } from "./ValueAxis";

type BarChartProps = ChartBaseProps & {
  /** Stack the series. Use only when the series are parts of a whole. */
  stacked?: boolean;
};

const MARGIN = { top: 18, right: 12, bottom: 28, left: 48 };
const MAX_SERIES = 4;
const LABEL_SPACE = 64;

/** Fills laid over the colour so bars differ without relying on it (series 2-4). */
function Patterns({ id }: { id: string }) {
  return (
    <defs>
      <pattern
        id={`${id}-1`}
        width="6"
        height="6"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <line className="ui-chart__pattern" x1="0" y1="0" x2="0" y2="6" />
      </pattern>
      <pattern id={`${id}-2`} width="6" height="6" patternUnits="userSpaceOnUse">
        <circle className="ui-chart__pattern-dot" cx="3" cy="3" r="1.2" />
      </pattern>
      <pattern id={`${id}-3`} width="6" height="6" patternUnits="userSpaceOnUse">
        <line className="ui-chart__pattern" x1="0" y1="3" x2="6" y2="3" />
      </pattern>
    </defs>
  );
}

/** Compare categories (days, units); bars start at zero. Each distinct `t` is one category. */
export function BarChart({ stacked = false, height = 240, ...props }: BarChartProps) {
  const { title, unit, period, updated } = props;
  const patternId = useId();
  const series = useMemo(() => props.series.slice(0, MAX_SERIES), [props.series]);
  const categories = useMemo(
    () => [...new Set(series.flatMap((item) => item.points.map((point) => point.t)))].sort((a, b) => a - b),
    [series],
  );
  const lookups = useMemo(
    () => series.map((item) => new Map(item.points.map((point) => [point.t, point.value]))),
    [series],
  );
  const { active, setActive, handlers } = useActivePoint(series.map(() => categories.length));
  const formatTime = props.formatTime ?? makeTimeFormatter(series);
  const formatValue = props.formatValue ?? defaultValueFormat;

  const valueAt = (s: number, c: number) => lookups[s]?.get(categories[c] ?? 0) ?? null;
  const totals = categories.map((_, c) => series.reduce((sum, _s, s) => sum + (valueAt(s, c) ?? 0), 0));
  const stackExtent = stacked ? extent([0, ...totals]) : undefined;
  const flat = extent([0, ...series.flatMap((_s, s) => categories.map((_c, c) => valueAt(s, c) ?? 0))]);
  const [low, high] = stackExtent ?? flat ?? [0, 1];
  const axis = niceTicks(low, high, 5);

  const readout = active
    ? `${series[active.series]?.label ?? ""}, ${formatFullTime(categories[active.index] ?? 0)}, ${withUnit(valueAt(active.series, active.index), unit, formatValue)}`
    : null;

  function pointer(x: number | null, width: number) {
    if (x === null || categories.length === 0) {
      setActive(null);
      return;
    }
    const band = (width - MARGIN.left - MARGIN.right) / categories.length;
    const index = Math.min(categories.length - 1, Math.max(0, Math.floor((x - MARGIN.left) / band)));
    setActive({ series: active?.series ?? 0, index });
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
          const left = MARGIN.left;
          const right = width - MARGIN.right;
          const y = linearScale([axis.min, axis.max], [height - MARGIN.bottom, MARGIN.top]);
          const band = (right - left) / categories.length;
          const slots = stacked ? 1 : series.length;
          const barWidth = (band * 0.7) / slots;
          const every = Math.max(1, Math.ceil(LABEL_SPACE / band));
          const base = y(0);
          return (
            <>
              <Patterns id={patternId} />
              <ValueAxis
                ticks={axis.ticks}
                y={y}
                left={left}
                right={right}
                unit={unit}
                format={formatValue}
              />
              {categories.map((t, c) => {
                const start = left + band * c + band * 0.15;
                let stackTop = 0;
                return (
                  <g key={t}>
                    {c % every === 0 && (
                      <text
                        className="ui-chart__tick"
                        x={left + band * (c + 0.5)}
                        y={height - 8}
                        textAnchor="middle"
                      >
                        {formatTime(t)}
                      </text>
                    )}
                    {series.map((item, s) => {
                      const value = valueAt(s, c);
                      if (value === null) return null;
                      const from = stacked ? stackTop : 0;
                      stackTop += value;
                      const to = stacked ? stackTop : value;
                      const top = Math.min(y(from), y(to));
                      const size = Math.max(Math.abs(y(from) - y(to)), value === 0 ? 0 : 1);
                      const x = stacked ? start : start + barWidth * s;
                      const isActive = active?.series === s && active.index === c;
                      return (
                        <g key={item.label} className={`ui-chart__s${s}`}>
                          <rect
                            className={isActive ? "ui-chart__bar ui-chart__bar--active" : "ui-chart__bar"}
                            x={x}
                            y={top}
                            width={barWidth}
                            height={size}
                          />
                          {s > 0 && (
                            <rect
                              className="ui-chart__overlay"
                              x={x}
                              y={top}
                              width={barWidth}
                              height={size}
                              fill={`url(#${patternId}-${s})`}
                            />
                          )}
                        </g>
                      );
                    })}
                  </g>
                );
              })}
              <line className="ui-chart__axis" x1={left} x2={right} y1={base} y2={base} />
            </>
          );
        }}
      </ChartPlot>
    </ChartFrame>
  );
}
