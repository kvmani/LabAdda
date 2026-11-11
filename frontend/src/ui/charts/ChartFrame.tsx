import { useState, type ReactNode } from "react";
import { Button } from "../Button";
import { EmptyState } from "../EmptyState";
import { Mark } from "./marks";
import "./charts.css";

type ChartFrameProps = {
  title: string;
  period: string;
  /** Shown as unknown when the caller does not know. */
  updated?: string;
  /** Series names for the legend; the legend appears only when there is more than one. */
  legend?: string[];
  /** True when nothing was measured; shows the empty state instead of the drawing. */
  empty: boolean;
  /** The same data as a table, shown by "View as table". */
  table: ReactNode;
  /** The drawing. Hidden while the table is shown. */
  children: ReactNode;
};

/**
 * Shared chart chrome (UX-09): title, period, last update, legend, empty state, and the
 * "View as table" toggle.
 */
export function ChartFrame({ title, period, updated, legend = [], empty, table, children }: ChartFrameProps) {
  const [asTable, setAsTable] = useState(false);
  return (
    <figure className="ui-chart">
      <figcaption className="ui-chart__head">
        <span className="ui-chart__title">{title}</span>
        <span className="ui-chart__meta">
          {period} · {updated ?? "Update time unknown"}
        </span>
      </figcaption>
      {empty ? (
        <EmptyState title="No data for this period">
          Nothing was measured for {period.toLowerCase()}.
        </EmptyState>
      ) : (
        <>
          <div className="ui-chart__tools">
            {legend.length > 1 && (
              <ul className="ui-chart__legend" aria-label="Legend">
                {legend.map((label, index) => (
                  <li key={label}>
                    <svg
                      className={`ui-chart__swatch ui-chart__s${index}`}
                      viewBox="0 0 12 12"
                      aria-hidden="true"
                    >
                      <Mark shape={index} x={6} y={6} size={4} />
                    </svg>
                    {label}
                  </li>
                ))}
              </ul>
            )}
            <Button size="sm" variant="quiet" onClick={() => setAsTable(!asTable)}>
              {asTable ? "View as chart" : "View as table"}
            </Button>
          </div>
          {asTable ? table : children}
        </>
      )}
    </figure>
  );
}
