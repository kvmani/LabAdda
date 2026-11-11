import { DataTable } from "../DataTable";
import { ChartFrame } from "./ChartFrame";
import { ChartPlot } from "./ChartPlot";
import { defaultValueFormat, withUnit } from "./format";
import { CELL_HEIGHT, HeatDrawing, TOP, heatTableColumns, type TableRow } from "./HeatDrawing";
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
    ? [
        rows[active.series] ?? "",
        columns[active.index] ?? "",
        withUnit(cell(active.series, active.index), unit, formatValue),
      ].join(", ")
    : null;

  const tableRows: TableRow[] = rows.map((label, r) => ({ label, cells: columns.map((_, c) => cell(r, c)) }));
  const tableColumns = heatTableColumns(columns, unit, formatValue);

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
        {(width) => <HeatDrawing {...{ width, rows, columns, cell, peak, active }} />}
      </ChartPlot>
    </ChartFrame>
  );
}
