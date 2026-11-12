import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { StatusPill, type HealthStatus } from "./StatusPill";
import "./display.css";

type StatTileProps = {
  label: string;
  /** The figure as text, already with its unit. Use words such as "Not measured" when there is none. */
  value: string;
  /** The span and freshness the figure covers, for example "Today. Updated 12 s ago". */
  note?: string;
  /** Shown as icon plus word beside the figure when it is anything but a plain measurement. */
  status?: HealthStatus;
  /** The page that lists what is behind the figure (UX-10: every number links to its list). */
  to: string;
  /** A Sparkline or other small trend drawing. */
  children?: ReactNode;
};

/** One dashboard figure with its trend, freshness and a link to the detail behind it (UX-10). */
export function StatTile({ label, value, note, status, to, children }: StatTileProps) {
  return (
    <div className="ui-stat-tile">
      <Link className="ui-stat-tile__label" to={to}>
        {label}
      </Link>
      <p className="ui-stat-tile__value">{value}</p>
      {status && <StatusPill status={status} />}
      {children}
      {note && <p className="ui-stat-tile__note">{note}</p>}
    </div>
  );
}
