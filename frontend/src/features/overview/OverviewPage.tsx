import { useCallback, useState } from "react";
import { BASE } from "../../config";
import { Button, Card, ErrorState, PageHeader, Skeleton, StatusPill, type HealthStatus } from "../../ui";
import { useNow, usePolledData } from "../admin/usePolledData";
import { formatAge } from "../health/model";
import { Attention } from "./Attention";
import { Charts } from "./Charts";
import { STALE_AFTER_SECONDS, POLL_MS, overallSentence } from "./model";
import { Tiles } from "./Tiles";
import type { Overview } from "./types";
import "./overview.css";

/** The console landing page (A6): is everything all right, and what needs me? Polls while visible. */
export function OverviewPage() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, fetchedAt, reload } = usePolledData<Overview>("/admin/overview", POLL_MS, onDenied);
  const now = useNow();
  const header = (
    <PageHeader
      title="Overview"
      scope="Is everything all right, and what needs you? Counts, sizes and times only; nobody's work is shown."
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
        <Skeleton label="Loading the overview" />
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
      <Tiles overview={data} now={now} />
      <Charts overview={data} updated={updated} />
    </>
  );
}
