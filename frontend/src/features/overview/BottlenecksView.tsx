import { Link } from "react-router-dom";
import type { Bottlenecks } from "./types";

type Props = {
  bottlenecks: Bottlenecks;
};

export function BottlenecksView({ bottlenecks }: Props) {
  const { storage, governance, performance, reliability } = bottlenecks;

  const maxStorage = Math.max(...storage.top_workspaces.map((w) => w.bytes), 1);

  return (
    <div className="bottlenecks-view">
      {/* 1. Storage Consumption Bottlenecks */}
      <section className="cockpit-panel" aria-label="Storage consumption analysis">
        <div className="cockpit-panel__header">
          <div>
            <h3 className="cockpit-panel__title">
              <span aria-hidden="true">💾</span> Storage Consumption by Workspace
            </h3>
            <p className="cockpit-panel__subtitle">
              Identifies workspaces utilizing the most disk space to anticipate quota needs
            </p>
          </div>
          <Link to="/admin/storage" className="cockpit-panel__action-link">
            Storage policy →
          </Link>
        </div>

        <div className="cockpit-panel__body">
          {!storage.top_workspaces.length ? (
            <p className="cockpit-muted">No storage usage recorded yet.</p>
          ) : (
            <div className="storage-bottleneck-list">
              {storage.top_workspaces.map((ws) => {
                const percent = Math.min(100, Math.round((ws.bytes / maxStorage) * 100));
                return (
                  <div key={ws.id} className="storage-bottleneck-item">
                    <div className="storage-bottleneck-item__meta">
                      <span className="storage-bottleneck-item__name">
                        {ws.kind === "project" ? "🚀 " : ws.kind === "org" ? "🏢 " : "👥 "}
                        {ws.name}
                      </span>
                      <span className="storage-bottleneck-item__size">{ws.formatted}</span>
                    </div>
                    <div
                      className="storage-bar"
                      role="progressbar"
                      aria-valuenow={percent}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div className="storage-bar__fill" style={{ width: `${percent}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="cockpit-note">💡 {storage.headroom_status}</p>
        </div>
      </section>

      {/* 2. Governance Bottlenecks */}
      <section className="cockpit-panel" aria-label="Administrative governance bottlenecks">
        <div className="cockpit-panel__header">
          <div>
            <h3 className="cockpit-panel__title">
              <span aria-hidden="true">🏛️</span> Governance & Leadership Attention
            </h3>
            <p className="cockpit-panel__subtitle">
              Workspaces without an active steward or Head can leave members without support
            </p>
          </div>
          <Link to="/admin/org" className="cockpit-panel__action-link">
            Assign leaders →
          </Link>
        </div>

        <div className="cockpit-panel__body">
          {governance.unstaffed_units_count === 0 && governance.unstaffed_projects_count === 0 ? (
            <div className="cockpit-banner cockpit-banner--ok">
              <span>✓ All research units and projects have assigned stewards and leaders.</span>
            </div>
          ) : (
            <div className="governance-bottlenecks-list">
              {governance.unstaffed_units_count > 0 && (
                <div className="gov-item">
                  <div className="gov-item__header">
                    <span className="cockpit-badge cockpit-badge--warn">
                      {governance.unstaffed_units_count} Units Need Stewards
                    </span>
                    <Link to="/admin/org" className="gov-item__btn">
                      Appoint Heads →
                    </Link>
                  </div>
                  <p className="gov-item__desc">{governance.unstaffed_units.join(", ")}</p>
                </div>
              )}

              {governance.unstaffed_projects_count > 0 && (
                <div className="gov-item">
                  <div className="gov-item__header">
                    <span className="cockpit-badge cockpit-badge--warn">
                      {governance.unstaffed_projects_count} Projects Need Stewards
                    </span>
                    <Link to="/admin/org" className="gov-item__btn">
                      Assign Stewards →
                    </Link>
                  </div>
                  <p className="gov-item__desc">{governance.unstaffed_projects.join(", ")}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* 3. Performance & System Latency */}
      <section className="cockpit-panel" aria-label="System response latency">
        <div className="cockpit-panel__header">
          <div>
            <h3 className="cockpit-panel__title">
              <span aria-hidden="true">⚡</span> System Responsiveness & Latency
            </h3>
            <p className="cockpit-panel__subtitle">
              Response time percentiles and operational connection health
            </p>
          </div>
          <Link to="/admin/health" className="cockpit-panel__action-link">
            Health probes →
          </Link>
        </div>

        <div className="cockpit-panel__body">
          <div className="perf-summary-row">
            <div className="perf-card">
              <span className="perf-card__label">Latency Status</span>
              <span className="perf-card__val">{performance.latency_status}</span>
            </div>
            <div className="perf-card">
              <span className="perf-card__label">p95 Response Time</span>
              <span className="perf-card__val">
                {performance.p95_latency_ms !== null
                  ? `${Math.round(performance.p95_latency_ms)} ms`
                  : "Not measured"}
              </span>
            </div>
            <div className="perf-card">
              <span className="perf-card__label">Target SLA</span>
              <span className="perf-card__val">&lt; 300 ms (Intranet)</span>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Operational Errors & Remediation Guidance */}
      <section className="cockpit-panel" aria-label="Operational error guidance">
        <div className="cockpit-panel__header">
          <div>
            <h3 className="cockpit-panel__title">
              <span aria-hidden="true">⚠️</span> System Diagnostic Guidance
            </h3>
            <p className="cockpit-panel__subtitle">
              Plain-English guidance designed for non-experienced administrators
            </p>
          </div>
          <Link to="/admin/events?state=open" className="cockpit-panel__action-link">
            All events ({reliability.open_events.length}) →
          </Link>
        </div>

        <div className="cockpit-panel__body">
          {!reliability.open_events.length ? (
            <div className="cockpit-banner cockpit-banner--ok">
              <span>✓ Zero active operational errors or warnings reported. System running cleanly.</span>
            </div>
          ) : (
            <ul className="remediation-list">
              {reliability.open_events.map((ev) => (
                <li key={ev.id} className="remediation-item">
                  <div className="remediation-item__top">
                    <span className={`cockpit-badge cockpit-badge--${ev.severity}`}>
                      {ev.severity.toUpperCase()}
                    </span>
                    <strong className="remediation-item__summary">{ev.summary}</strong>
                  </div>
                  <div className="remediation-item__advice">
                    <span className="remediation-item__advice-label">Recommended action:</span>{" "}
                    {ev.recommendation}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
