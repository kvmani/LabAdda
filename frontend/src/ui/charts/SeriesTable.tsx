import { DataTable, type Column } from "../DataTable";
import { defaultValueFormat, formatFullTime } from "./format";
import type { Series } from "./types";

type Row = { t: number; values: (number | null)[] };

type SeriesTableProps = {
  title: string;
  series: Series[];
  unit?: string;
  formatValue?: (value: number) => string;
  formatTime?: (t: number) => string;
};

/** The chart's data as a table: the "View as table" alternative for every time-based chart. */
export function SeriesTable({ title, series, unit, formatValue, formatTime }: SeriesTableProps) {
  const format = formatValue ?? defaultValueFormat;
  const times = [...new Set(series.flatMap((item) => item.points.map((point) => point.t)))].sort(
    (a, b) => a - b,
  );
  const lookups = series.map((item) => new Map(item.points.map((point) => [point.t, point.value])));
  const rows: Row[] = times.map((t) => ({ t, values: lookups.map((lookup) => lookup.get(t) ?? null) }));
  const columns: Column<Row>[] = [
    {
      key: "time",
      header: "Time",
      render: (row) => (formatTime ?? formatFullTime)(row.t),
      sortValue: (row) => row.t,
    },
    ...series.map((item, index) => ({
      key: `series-${index}`,
      header: unit ? `${item.label} (${unit})` : item.label,
      align: "end" as const,
      render: (row: Row) => {
        const value = row.values[index] ?? null;
        return value === null ? "No data" : format(value);
      },
      sortValue: (row: Row) => row.values[index] ?? Number.NEGATIVE_INFINITY,
    })),
  ];
  return (
    <DataTable
      caption={`${title}, as a table`}
      columns={columns}
      rows={rows}
      rowKey={(row) => String(row.t)}
      initialSort={{ key: "time", direction: "ascending" }}
    />
  );
}
