import { useMemo } from "react";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { downsample } from "./downsample";
import { defaultValueFormat, formatFullTime, hasNoData, makeTimeFormatter, withUnit } from "./format";
import { extent, linearScale, niceTicks } from "./scale";
import { SeriesTable } from "./SeriesTable";
import type { ChartBaseProps } from "./types";
import { useActivePoint } from "./useActivePoint";
import { MARGIN, TimeDrawing } from "./TimeDrawing";

type TimeChartProps = ChartBaseProps & { area: boolean };

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
      ? [
          series[active.series]?.label ?? "",
          formatFullTime(point.t),
          withUnit(point.value, unit, formatValue),
        ].join(", ")
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
        {(width) => (
          <TimeDrawing
            {...{ width, height, drawn, area, axis, times, unit, formatTime, formatValue, active }}
          />
        )}
      </ChartPlot>
    </ChartFrame>
  );
}
