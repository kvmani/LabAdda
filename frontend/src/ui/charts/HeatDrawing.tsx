import type { Column } from "../DataTable";
import type { Active } from "./useActivePoint";

export const LEFT = 44;
export const TOP = 22;
export const CELL_HEIGHT = 22;
const LABEL_SPACE = 28;

export type TableRow = { label: string; cells: (number | null)[] };

/** Table columns for the "View as table" alternative: one per grid column. */
export function heatTableColumns(
  columns: string[],
  unit: string | undefined,
  formatValue: (value: number) => string,
): Column<TableRow>[] {
  return [
    { key: "row", header: "Day", render: (row) => row.label },
    ...columns.map((label, c) => ({
      key: `c${c}`,
      header: unit ? `${label} (${unit})` : label,
      align: "end" as const,
      render: (row: TableRow) => {
        const value = row.cells[c] ?? null;
        return value === null ? "No data" : formatValue(value);
      },
    })),
  ];
}

type HeatDrawingProps = {
  width: number;
  rows: string[];
  columns: string[];
  cell: (r: number, c: number) => number | null;
  /** Largest value; the darkest cell. */
  peak: number;
  active: Active | null;
};

/** The SVG contents of the heat grid: labels and one cell per row and column. */
export function HeatDrawing({ width, rows, columns, cell, peak, active }: HeatDrawingProps) {
  const size = (width - LEFT) / columns.length;
  const every = Math.max(1, Math.ceil(LABEL_SPACE / size));
  return (
    <>
      {columns.map((label, c) =>
        c % every === 0 ? (
          <text key={label} className="ui-chart__tick" x={LEFT + size * (c + 0.5)} y={12} textAnchor="middle">
            {label}
          </text>
        ) : null,
      )}
      {rows.map((label, r) => (
        <g key={label}>
          <text
            className="ui-chart__tick"
            x={LEFT - 6}
            y={TOP + CELL_HEIGHT * (r + 0.5)}
            textAnchor="end"
            dominantBaseline="middle"
          >
            {label}
          </text>
          {columns.map((name, c) => {
            const value = cell(r, c);
            const isActive = active?.series === r && active.index === c;
            const className = [
              "ui-chart__cell",
              value === null && "ui-chart__cell--gap",
              isActive && "ui-chart__cell--active",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <rect
                key={name}
                className={className}
                x={LEFT + size * c + 1}
                y={TOP + CELL_HEIGHT * r + 1}
                width={Math.max(size - 2, 1)}
                height={CELL_HEIGHT - 2}
                fillOpacity={value === null || peak === 0 ? 0 : 0.1 + 0.9 * (value / peak)}
              />
            );
          })}
        </g>
      ))}
    </>
  );
}
