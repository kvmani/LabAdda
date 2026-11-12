import { useMemo } from "react";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { defaultValueFormat, formatFullTime, hasNoData, makeTimeFormatter, withUnit } from "./format";
import { useBarData } from "./barData";
import { SeriesTable } from "./SeriesTable";
import type { ChartBaseProps } from "./types";
import { useActivePoint } from "./useActivePoint";
import { BarDrawing, MARGIN } from "./BarDrawing";

type BarChartProps = ChartBaseProps & {
  /** Stack the series. Use only when the series are parts of a whole. */
  stacked?: boolean;
};

const MAX_SERIES = 4;

/** Compare categories (days, units); bars start at zero. Each distinct `t` is one category. */
export function BarChart({ stacked = false, height = 240, ...props }: BarChartProps) {
  const { title, unit, period, updated } = props;
  const series = useMemo(() => props.series.slice(0, MAX_SERIES), [props.series]);
  const { categories, valueAt, axis } = useBarData(series, stacked);
  const { active, setActive, handlers } = useActivePoint(series.map(() => categories.length));
  const formatTime = props.formatTime ?? makeTimeFormatter(series);
  const formatValue = props.formatValue ?? defaultValueFormat;

  const readout = active
    ? [
        series[active.series]?.label ?? "",
        (props.formatTime ?? formatFullTime)(categories[active.index] ?? 0),
        withUnit(valueAt(active.series, active.index), unit, formatValue),
      ].join(", ")
    : null;

  function pointer(x: number | null, width: number) {
    const band = (width - MARGIN.left - MARGIN.right) / categories.length;
    const at = Math.floor(((x ?? 0) - MARGIN.left) / band);
    const index = Math.min(categories.length - 1, Math.max(0, at));
    setActive(x === null || categories.length === 0 ? null : { series: active?.series ?? 0, index });
  }

  return (
    <ChartFrame
      title={title}
      period={period}
      updated={updated}
      legend={series.map((item) => item.label)}
      empty={series.length === 0 || hasNoData(series)}
      table={<SeriesTable {...{ title, series, unit, formatValue, formatTime: props.formatTime }} />}
    >
      <ChartPlot
        label={`${title}, ${period}`}
        height={height}
        readout={readout}
        handlers={handlers}
        onPointer={pointer}
      >
        {(width) => (
          <BarDrawing
            {...{
              width,
              height,
              categories,
              series,
              valueAt,
              stacked,
              axis,
              unit,
              formatTime,
              formatValue,
              active,
            }}
          />
        )}
      </ChartPlot>
    </ChartFrame>
  );
}
