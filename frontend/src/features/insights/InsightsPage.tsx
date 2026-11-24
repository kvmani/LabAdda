import { useCallback, useState } from "react";
import { useFilterParams } from "../../useFilterParams";
import { BASE } from "../../config";
import { ErrorState, PageHeader, Select, Skeleton, Tabs } from "../../ui";
import { formatAge } from "../health/model";
import { useNow, usePolledData } from "../admin/usePolledData";
import { HORIZONS, parseSpan, parseWeeks, SPANS } from "./model";
import { PerformanceView } from "./PerformanceView";
import { TrendsView } from "./TrendsView";
import type { Performance, Trends } from "./types";
import "./insights.css";

const REFRESH_MS = 60_000;
const TABS = [
  { id: "trends", label: "Feature trends" },
  { id: "performance", label: "Performance" },
];

/** Insights: how use of each feature is changing, and how fast and reliable the site is. */
export function InsightsPage() {
  const { params, apply } = useFilterParams([], []);
  const view = params.get("view") === "performance" ? "performance" : "trends";
  const weeks = parseWeeks(params.get("weeks"));
  const span = parseSpan(params.get("span"));
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const trends = usePolledData<Trends>(
    view === "trends" ? `/admin/insights/trends?weeks=${weeks}` : null,
    REFRESH_MS,
    onDenied,
  );
  const perf = usePolledData<Performance>(
    view === "performance" ? `/admin/insights/performance?span=${span}` : null,
    REFRESH_MS,
    onDenied,
  );
  const now = useNow(10_000);
  const set = (key: string, value: string) => apply((next) => next.set(key, value));

  const header = (
    <PageHeader
      title="Insights"
      scope="Which features are growing or fading, and how fast and reliable LabAdda is. Counts and timings only."
      helpHref={`${BASE}/help/admin/insights-page`}
    />
  );
  if (denied)
    return (
      <>
        {header}
        <ErrorState
          title="Your administration access changed"
          message="Insights have been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );

  const current = view === "trends" ? trends : perf;
  const updated =
    current.fetchedAt === null ? undefined : `Updated ${formatAge((now - current.fetchedAt) / 1000)}`;
  const spanLabel = SPANS.find((option) => option.value === span)?.label ?? "";
  let body;
  if (current.error && !current.data) body = <ErrorState message={current.error} onRetry={current.reload} />;
  else if (view === "trends")
    body = trends.data ? (
      <TrendsView trends={trends.data} updated={updated} />
    ) : (
      <Skeleton label="Loading trends" />
    );
  else
    body = perf.data ? (
      <PerformanceView data={perf.data} period={spanLabel} updated={updated} />
    ) : (
      <Skeleton label="Loading performance figures" />
    );

  return (
    <>
      {header}
      <Tabs label="Insights views" tabs={TABS} selected={view} onSelect={(id) => set("view", id)}>
        <div className="insights-controls">
          {view === "trends" ? (
            <Select
              label="Period"
              value={weeks}
              options={HORIZONS}
              onChange={(event) => set("weeks", parseWeeks(event.target.value))}
            />
          ) : (
            <Select
              label="Period"
              value={span}
              options={SPANS}
              onChange={(event) => set("span", parseSpan(event.target.value))}
            />
          )}
          {updated && <p className="insights-muted">{updated}</p>}
        </div>
        {current.error && current.data && (
          <p className="insights-warning" role="alert">
            These figures could not be refreshed and may be out of date. {current.error}
          </p>
        )}
        {body}
      </Tabs>
    </>
  );
}
