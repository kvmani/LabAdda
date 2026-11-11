import type { Scale } from "./scale";

type ValueAxisProps = {
  ticks: number[];
  y: Scale;
  left: number;
  right: number;
  unit?: string;
  format: (value: number) => string;
};

/** Horizontal grid lines with value labels and the unit above the axis. */
export function ValueAxis({ ticks, y, left, right, unit, format }: ValueAxisProps) {
  return (
    <g>
      {unit && (
        <text className="ui-chart__tick" x={0} y={8}>
          {unit}
        </text>
      )}
      {ticks.map((tick, index) => (
        <g key={tick}>
          <line
            className={index === 0 ? "ui-chart__axis" : "ui-chart__grid"}
            x1={left}
            x2={right}
            y1={y(tick)}
            y2={y(tick)}
          />
          <text
            className="ui-chart__tick"
            x={left - 6}
            y={y(tick)}
            textAnchor="end"
            dominantBaseline="middle"
          >
            {format(tick)}
          </text>
        </g>
      ))}
    </g>
  );
}
