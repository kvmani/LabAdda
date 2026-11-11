import { useId } from "react";
import { linearScale, type NiceTicks } from "./scale";
import type { Series } from "./types";
import type { Active } from "./useActivePoint";
import { ValueAxis } from "./ValueAxis";

export const MARGIN = { top: 26, right: 12, bottom: 28, left: 48 };
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

type BarProps = {
  series: number;
  patternId: string;
  isActive: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
};

/** One bar; series after the first get a pattern so they differ without colour. */
function Bar({ series, patternId, isActive, ...box }: BarProps) {
  return (
    <g className={`ui-chart__s${series}`}>
      <rect className={isActive ? "ui-chart__bar ui-chart__bar--active" : "ui-chart__bar"} {...box} />
      {series > 0 && <rect className="ui-chart__overlay" {...box} fill={`url(#${patternId}-${series})`} />}
    </g>
  );
}

type BarDrawingProps = {
  width: number;
  height: number;
  categories: number[];
  series: Series[];
  /** Value of series `s` in category `c`, or null for a gap. */
  valueAt: (s: number, c: number) => number | null;
  stacked: boolean;
  axis: NiceTicks;
  unit?: string;
  formatTime: (t: number) => string;
  formatValue: (value: number) => string;
  active: Active | null;
};

/** The SVG contents of a bar chart: axis, grouped or stacked bars, category labels. */
export function BarDrawing(props: BarDrawingProps) {
  const { width, height, categories, series, valueAt, stacked, axis, active } = props;
  const patternId = useId();
  const left = MARGIN.left;
  const right = width - MARGIN.right;
  const y = linearScale([axis.min, axis.max], [height - MARGIN.bottom, MARGIN.top]);
  const band = (right - left) / categories.length;
  const barWidth = (band * 0.7) / (stacked ? 1 : series.length);
  const every = Math.max(1, Math.ceil(LABEL_SPACE / band));
  return (
    <>
      <Patterns id={patternId} />
      <ValueAxis
        ticks={axis.ticks}
        y={y}
        left={left}
        right={right}
        unit={props.unit}
        format={props.formatValue}
      />
      {categories.map((t, c) => {
        const start = left + band * c + band * 0.15;
        let stackTop = 0;
        return (
          <g key={t}>
            {c % every === 0 && (
              <text className="ui-chart__tick" x={left + band * (c + 0.5)} y={height - 8} textAnchor="middle">
                {props.formatTime(t)}
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
                <Bar
                  key={item.label}
                  {...{ series: s, patternId, isActive, x, y: top, width: barWidth, height: size }}
                />
              );
            })}
          </g>
        );
      })}
      <line className="ui-chart__axis" x1={left} x2={right} y1={y(0)} y2={y(0)} />
    </>
  );
}
