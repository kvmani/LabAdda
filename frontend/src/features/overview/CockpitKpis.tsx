import { Link } from "react-router-dom";
import type { CockpitKPIs } from "./types";

type Props = {
  kpis: CockpitKPIs;
};

export function CockpitKpis({ kpis }: Props) {
  return (
    <section className="cockpit-kpis" aria-label="360-degree Key Performance Indicators">
      {/* 1. Enabled Accounts KPI */}
      <div className="cockpit-kpi-card">
        <div className="cockpit-kpi-card__header">
          <span className="cockpit-kpi-card__icon" aria-hidden="true">
            👥
          </span>
          <span className="cockpit-kpi-card__title">Enabled Accounts</span>
        </div>
        <div className="cockpit-kpi-card__value">
          {kpis.active_accounts}
          <span className="cockpit-kpi-card__unit"> / {kpis.total_accounts}</span>
        </div>
        <div className="cockpit-kpi-card__sub">
          <span className="cockpit-badge cockpit-badge--ok">{kpis.adoption_rate}% Enabled</span>
          <span className="cockpit-kpi-card__note">Across {kpis.total_workspaces} workspaces</span>
        </div>
      </div>

      {/* 2. Collaboration Velocity KPI */}
      <div className="cockpit-kpi-card">
        <div className="cockpit-kpi-card__header">
          <span className="cockpit-kpi-card__icon" aria-hidden="true">
            🚀
          </span>
          <span className="cockpit-kpi-card__title">Collaboration Items</span>
        </div>
        <div className="cockpit-kpi-card__value">
          {kpis.total_collaboration_items ??
            (kpis.collaboration_state === "suppressed" ? "Protected" : "Not measured")}
        </div>
        <div className="cockpit-kpi-card__sub">
          <span className="cockpit-badge cockpit-badge--info">Published activity</span>
          <span className="cockpit-kpi-card__note">Shared items created in the last 7 days</span>
        </div>
      </div>

      {/* 3. Storage Footprint KPI */}
      <div className="cockpit-kpi-card">
        <div className="cockpit-kpi-card__header">
          <span className="cockpit-kpi-card__icon" aria-hidden="true">
            💾
          </span>
          <span className="cockpit-kpi-card__title">Recorded Shared Storage</span>
        </div>
        <div className="cockpit-kpi-card__value">{kpis.total_storage_formatted}</div>
        <div className="cockpit-kpi-card__sub">
          <span className="cockpit-badge cockpit-badge--info">Observation only</span>
          <Link to="/admin/storage" className="cockpit-kpi-card__link">
            Storage details →
          </Link>
        </div>
      </div>

      {/* 4. Operational Events KPI */}
      <div className="cockpit-kpi-card">
        <div className="cockpit-kpi-card__header">
          <span className="cockpit-kpi-card__icon" aria-hidden="true">
            🛡️
          </span>
          <span className="cockpit-kpi-card__title">System Events</span>
        </div>
        <div className="cockpit-kpi-card__value">
          {kpis.open_events_count}
          <span className="cockpit-kpi-card__unit"> open</span>
        </div>
        <div className="cockpit-kpi-card__sub">
          {kpis.open_events_count === 0 ? (
            <span className="cockpit-badge cockpit-badge--ok">All nominal</span>
          ) : (
            <span className="cockpit-badge cockpit-badge--warn">
              {kpis.events_by_severity.critical ? "Critical pending" : "Warnings to review"}
            </span>
          )}
          <Link to="/admin/events?state=open" className="cockpit-kpi-card__link">
            Action log →
          </Link>
        </div>
      </div>
    </section>
  );
}
