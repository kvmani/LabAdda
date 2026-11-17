import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { BASE } from "../../config";
import { Button, Card, ErrorState, PageHeader, Skeleton, StatusPill, type HealthStatus } from "../../ui";
import { useNow, usePolledData } from "../admin/usePolledData";
import { formatAge } from "../health/model";
import { Attention } from "./Attention";
import { BottlenecksView } from "./BottlenecksView";
import { Charts } from "./Charts";
import { CockpitKpis } from "./CockpitKpis";
import { STALE_AFTER_SECONDS, POLL_MS, overallSentence } from "./model";
import { PopularWorkspaces } from "./PopularWorkspaces";
import { Tiles } from "./Tiles";
import type { Overview } from "./types";
import { UsagePatternsView } from "./UsagePatternsView";
import "./overview.css";

type TabId = "overview" | "trends" | "bottlenecks" | "diagnostics";

/** The console landing page (A6): 360-degree Cockpit and bottleneck discovery engine. Polls while visible. */
export function OverviewPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, fetchedAt, reload } = usePolledData<Overview>("/admin/overview", POLL_MS, onDenied);
  const now = useNow();

  const header = (
    <PageHeader
      title="360° System Cockpit"
      scope="Real-time telemetry, bottleneck detection, usage trends and operational guidance for administrators."
      helpHref={`${BASE}/help/admin/overview-page`}
      action={
        <Button icon="refresh" onClick={reload}>
          Check now
        </Button>
      }
    />
  );

  if (denied)
    return (
      <>
        {header}
        <ErrorState
          title="Your administration access changed"
          message="The overview has been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );

  if (error && !data)
    return (
      <>
        {header}
        <ErrorState message={error} onRetry={reload} />
      </>
    );

  if (!data)
    return (
      <>
        {header}
        <Skeleton label="Loading the system cockpit" />
      </>
    );

  const age = fetchedAt === null ? 0 : (now - fetchedAt) / 1000;
  const old = age > STALE_AFTER_SECONDS;
  // Old figures are never presented as the current state of the site.
  const overall: HealthStatus = old ? "stale" : data.overall;
  const updated = `Updated ${formatAge(age)}`;

  return (
    <>
      {header}
      {error && (
        <p className="overview-warning" role="alert">
          The overview could not be refreshed. The figures below are from {formatAge(age)}.
        </p>
      )}

      {/* 360-degree Top-Level KPIs */}
      {data.cockpit && <CockpitKpis kpis={data.cockpit.kpis} />}

      {/* Cockpit Navigation Tabs */}
      <nav className="cockpit-tabs-nav" aria-label="Cockpit views">
        <div className="cockpit-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            id="tab-overview"
            aria-selected={activeTab === "overview"}
            aria-controls="panel-overview"
            className={`cockpit-tab-btn ${activeTab === "overview" ? "cockpit-tab-btn--active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            <span aria-hidden="true">🌐</span> 360° Overview
          </button>
          <button
            type="button"
            role="tab"
            id="tab-trends"
            aria-selected={activeTab === "trends"}
            aria-controls="panel-trends"
            className={`cockpit-tab-btn ${activeTab === "trends" ? "cockpit-tab-btn--active" : ""}`}
            onClick={() => setActiveTab("trends")}
          >
            <span aria-hidden="true">📈</span> Usage Trends & Popularity
          </button>
          <button
            type="button"
            role="tab"
            id="tab-bottlenecks"
            aria-selected={activeTab === "bottlenecks"}
            aria-controls="panel-bottlenecks"
            className={`cockpit-tab-btn ${activeTab === "bottlenecks" ? "cockpit-tab-btn--active" : ""}`}
            onClick={() => setActiveTab("bottlenecks")}
          >
            <span aria-hidden="true">⚡</span> Bottlenecks & SLA
          </button>
          <button
            type="button"
            role="tab"
            id="tab-diagnostics"
            aria-selected={activeTab === "diagnostics"}
            aria-controls="panel-diagnostics"
            className={`cockpit-tab-btn ${activeTab === "diagnostics" ? "cockpit-tab-btn--active" : ""}`}
            onClick={() => setActiveTab("diagnostics")}
          >
            <span aria-hidden="true">🛡️</span> Action & Diagnostics
            {data.cockpit?.bottlenecks.reliability.open_events.length ? (
              <span className="cockpit-tab-badge">
                {data.cockpit.bottlenecks.reliability.open_events.length}
              </span>
            ) : null}
          </button>
        </div>
      </nav>

      {/* Tab Panel 1: 360° Overview */}
      {activeTab === "overview" && (
        <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" className="cockpit-tabpanel">
          <section className={`overview-overall overview-overall--${overall}`} aria-label="Overall state">
            <StatusPill status={overall} />
            <p className="overview-overall__text">
              {old ? "These figures are out of date." : overallSentence(data.overall, data.attention.length)}
            </p>
            <p className="overview-overall__time">{updated}</p>
          </section>

          <Card title="Needs attention">
            <Attention entries={data.attention} healthy={data.overall === "healthy"} />
          </Card>

          {data.cockpit && data.cockpit.popular_workspaces.length > 0 && (
            <Card title="Most Active Collaboration Workspaces">
              <PopularWorkspaces workspaces={data.cockpit.popular_workspaces.slice(0, 5)} />
            </Card>
          )}

          <Tiles overview={data} now={now} />
          <Charts overview={data} updated={updated} />
        </div>
      )}

      {/* Tab Panel 2: Usage Trends & Popularity */}
      {activeTab === "trends" && (
        <div id="panel-trends" role="tabpanel" aria-labelledby="tab-trends" className="cockpit-tabpanel">
          {data.cockpit && (
            <UsagePatternsView
              patterns={data.cockpit.usage_patterns.feature_distribution}
              peakSummary={data.cockpit.usage_patterns.peak_summary}
            />
          )}

          {data.cockpit && (
            <Card title="Top Workspaces by Collaboration Volume">
              <PopularWorkspaces workspaces={data.cockpit.popular_workspaces} />
            </Card>
          )}

          <Charts overview={data} updated={updated} />
        </div>
      )}

      {/* Tab Panel 3: Bottlenecks & SLA */}
      {activeTab === "bottlenecks" && (
        <div
          id="panel-bottlenecks"
          role="tabpanel"
          aria-labelledby="tab-bottlenecks"
          className="cockpit-tabpanel"
        >
          {data.cockpit ? (
            <BottlenecksView bottlenecks={data.cockpit.bottlenecks} />
          ) : (
            <p className="cockpit-muted">Bottleneck telemetry unavailable.</p>
          )}
        </div>
      )}

      {/* Tab Panel 4: Action & Diagnostics */}
      {activeTab === "diagnostics" && (
        <div
          id="panel-diagnostics"
          role="tabpanel"
          aria-labelledby="tab-diagnostics"
          className="cockpit-tabpanel"
        >
          <section className="cockpit-panel" aria-label="Administrator action guide">
            <div className="cockpit-panel__header">
              <div>
                <h3 className="cockpit-panel__title">
                  <span aria-hidden="true">📋</span> System Diagnostic & Action Center
                </h3>
                <p className="cockpit-panel__subtitle">
                  Proactive recommendations for non-experienced administrators to keep LabAdda healthy
                </p>
              </div>
            </div>

            <div className="cockpit-panel__body">
              <div className="diagnostic-guide-grid">
                <div className="diagnostic-guide-card">
                  <div className="diagnostic-guide-card__head">
                    <span className="diagnostic-guide-card__icon" aria-hidden="true">
                      💾
                    </span>
                    <h4>Storage & Content Management</h4>
                  </div>
                  <p>
                    Check storage headroom weekly. LabAdda keeps data indefinitely; archive inactive projects
                    if disk capacity drops below 15%.
                  </p>
                  <Link to="/admin/storage" className="diagnostic-guide-card__link">
                    Review storage consumption →
                  </Link>
                </div>

                <div className="diagnostic-guide-card">
                  <div className="diagnostic-guide-card__head">
                    <span className="diagnostic-guide-card__icon" aria-hidden="true">
                      🏛️
                    </span>
                    <h4>Leadership & Governance</h4>
                  </div>
                  <p>
                    Ensure every Division and Project has at least one active steward assigned. Stewards
                    curate noticeboards and guide team members.
                  </p>
                  <Link to="/admin/org" className="diagnostic-guide-card__link">
                    Appoint stewards & leaders →
                  </Link>
                </div>

                <div className="diagnostic-guide-card">
                  <div className="diagnostic-guide-card__head">
                    <span className="diagnostic-guide-card__icon" aria-hidden="true">
                      🔒
                    </span>
                    <h4>Air-Gap & Backup Safety</h4>
                  </div>
                  <p>
                    Verify that daily database dumps succeed and are verified. No intranet asset ever contacts
                    external networks.
                  </p>
                  <Link to="/admin/backups" className="diagnostic-guide-card__link">
                    Inspect backup archives →
                  </Link>
                </div>

                <div className="diagnostic-guide-card">
                  <div className="diagnostic-guide-card__head">
                    <span className="diagnostic-guide-card__icon" aria-hidden="true">
                      ⚡
                    </span>
                    <h4>Response Time & Capacity</h4>
                  </div>
                  <p>
                    Intranet latency should stay under 300 ms. If latency spikes, check Postgres database
                    connections and vacuum status.
                  </p>
                  <Link to="/admin/health" className="diagnostic-guide-card__link">
                    Run subsystem health probes →
                  </Link>
                </div>
              </div>

              {data.cockpit && data.cockpit.bottlenecks.reliability.open_events.length > 0 && (
                <div className="open-events-section">
                  <h4 className="open-events-section__title">
                    Active Operational Events Requiring Action (
                    {data.cockpit.bottlenecks.reliability.open_events.length})
                  </h4>
                  <ul className="remediation-list">
                    {data.cockpit.bottlenecks.reliability.open_events.map((ev) => (
                      <li key={ev.id} className="remediation-item">
                        <div className="remediation-item__top">
                          <span className={`cockpit-badge cockpit-badge--${ev.severity}`}>
                            {ev.severity.toUpperCase()}
                          </span>
                          <span className="remediation-item__component">[{ev.component}]</span>
                          <strong className="remediation-item__summary">{ev.summary}</strong>
                        </div>
                        <div className="remediation-item__advice">
                          <span className="remediation-item__advice-label">Recommended action:</span>{" "}
                          {ev.recommendation}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  );
}
