import { useId, useMemo, useState, type ReactNode } from "react";
import { EmptyState } from "./EmptyState";
import { Icon } from "./Icon";
import { Skeleton } from "./Skeleton";
import "./base.css";
import "./table.css";

export type Column<Row> = {
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  /** Give a sort value to make the column sortable. */
  sortValue?: (row: Row) => string | number;
  align?: "start" | "end";
};

type SortState = { key: string; direction: "ascending" | "descending" };

type DataTableProps<Row> = {
  /** Names the table and its scrolling region. */
  caption: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  initialSort?: SortState;
  loading?: boolean;
  /** Shown instead of the table when there are no rows. */
  empty?: { title: string; body?: ReactNode; action?: ReactNode };
  /** Content under the table, such as a "Load more" button. */
  footer?: ReactNode;
};

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

function compare(left: string | number, right: string | number): number {
  if (typeof left === "number" && typeof right === "number") return left - right;
  return collator.compare(String(left), String(right));
}

/** An accessible data table with sortable columns, loading and empty states (UX-02). */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  initialSort,
  loading = false,
  empty,
  footer,
}: DataTableProps<Row>) {
  const [sort, setSort] = useState<SortState | undefined>(initialSort);
  const captionId = useId();

  const sorted = useMemo(() => {
    const column = columns.find((candidate) => candidate.key === sort?.key);
    if (!sort || !column?.sortValue) return rows;
    const value = column.sortValue;
    const ordered = [...rows].sort((left, right) => compare(value(left), value(right)));
    return sort.direction === "ascending" ? ordered : ordered.reverse();
  }, [rows, columns, sort]);

  function toggle(key: string) {
    setSort((current) =>
      current?.key === key && current.direction === "ascending"
        ? { key, direction: "descending" }
        : { key, direction: "ascending" },
    );
  }

  if (loading) return <Skeleton lines={4} label={`Loading ${caption.toLowerCase()}…`} />;
  if (rows.length === 0 && empty) {
    return (
      <EmptyState title={empty.title} action={empty.action}>
        {empty.body}
      </EmptyState>
    );
  }

  const sortedColumn = columns.find((column) => column.key === sort?.key);
  return (
    <div className="ui-table">
      <div className="ui-table__scroll" role="region" aria-labelledby={captionId} tabIndex={0}>
        <table>
          <caption id={captionId} className="ui-table__caption">
            {caption}
          </caption>
          <thead>
            <tr>
              {columns.map((column) => {
                const direction = sort?.key === column.key ? sort.direction : undefined;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={column.sortValue ? (direction ?? "none") : undefined}
                    className={column.align === "end" ? "ui-table__cell--end" : undefined}
                  >
                    {column.sortValue ? (
                      <button type="button" className="ui-table__sort" onClick={() => toggle(column.key)}>
                        <span>{column.header}</span>
                        <Icon name={direction === "descending" ? "arrow-down" : "arrow-up"} size="sm" />
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column) => (
                  <td key={column.key} className={column.align === "end" ? "ui-table__cell--end" : undefined}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ui-visually-hidden" role="status" aria-live="polite">
        {sort && sortedColumn ? `Sorted by ${sortedColumn.header}, ${sort.direction}` : ""}
      </p>
      {footer && <div className="ui-table__footer">{footer}</div>}
    </div>
  );
}
