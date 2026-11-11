import { DataTable, type Column } from "../DataTable";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { defaultValueFormat, withUnit } from "./format";
import { useActivePoint } from "./useActivePoint";

type HeatGridProps = {
  title: string;
  period: string;
  updated?: string;
  /** One label per row, for example the weekdays. */
  rows: string[];
  /** One label per column, for example the hours. */
  columns: string[];
  /** `values[row][column]`; null where nothing was measured, drawn as an empty dashed cell. */
  values: (number | null)[][];
  unit?: string;
  formatValue?: (value: number) => string;
};

const LEFT = 44;
const TOP = 22;
const CELL_HEIGHT = 22;
const LABEL_SPACE = 28;

type TableRow = { label: string; cells: (number | null)[] };

/** Activity by weekday and hour: darker means more. Read it with the arrow keys or as a table. */
export function HeatGrid({
  title,
  period,
  updated,
  rows,
  columns,
  values,
  unit,
  formatValue = defaultValueFormat,
}: HeatGridProps) {
  const { active, handlers } = useActivePoint(rows.map(() => columns.length));
  const cell = (r: number, c: number) => values[r]?.[c] ?? null;
  const peak = Math.max(0, ...values.flatMap((row) => row.map((value) => value ?? 0)));
  const empty =
    rows.length === 0 || columns.length === 0 || values.every((row) => row.every((value) => value === null));
  const readout = active
    ? `${rows[active.series] ?? ""}, ${columns[active.index] ?? ""}, ${withUnit(cell(active.series, active.index), unit, formatValue)}`
    : null;

  const tableRows: TableRow[] = rows.map((label, r) => ({ label, cells: columns.map((_, c) => cell(r, c)) }));
  const tableColumns: Column<TableRow>[] = [
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

  return (
    <ChartFrame
      title={title}
      period={period}
      updated={updated}
      empty={empty}
      table={
        <DataTable
          caption={`${title}, as a table`}
          columns={tableColumns}
          rows={tableRows}
          rowKey={(row) => row.label}
        />
      }
    >
      <ChartPlot
        label={`${title}, ${period}`}
        height={TOP + rows.length * CELL_HEIGHT}
        readout={readout}
        handlers={handlers}
      >
        {(width) => {
          const size = (width - LEFT) / columns.length;
          const every = Math.max(1, Math.ceil(LABEL_SPACE / size));
          return (
            <>
              {columns.map((label, c) =>
                c % every === 0 ? (
                  <text
                    key={label}
                    className="ui-chart__tick"
                    x={LEFT + size * (c + 0.5)}
                    y={12}
                    textAnchor="middle"
                  >
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
        }}
      </ChartPlot>
    </ChartFrame>
  );
}
