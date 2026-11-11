import { useCallback, useState } from "react";
import { BASE } from "../../config";
import { Button, ErrorState, PageHeader, Skeleton, StatusPill } from "../../ui";
import { usePolledData, useNow } from "../admin/usePolledData";
import { HealthCard } from "./HealthCard";
import { effectiveStatus, formatAge, overallSentence } from "./model";
import type { HealthReport } from "./types";
import "./health.css";

const POLL_MS = 15_000;

/** Live system health (AD-07): polls every 15 s while visible and says when figures are old. */
export function HealthPage() {
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, fetchedAt, reload } = usePolledData<HealthReport>("/admin/health", POLL_MS, onDenied);
  const now = useNow();
  const header = (
    <PageHeader
      title="System health"
      scope="How the server is doing right now. Counts, sizes and times only; nobody's work is shown."
      helpHref={`${BASE}/help/admin/system-health`}
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
          message="Health figures have been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );
  const sinceFetch = fetchedAt === null ? 0 : (now - fetchedAt) / 1000;
  const items = (data?.items ?? []).map((item) => {
    const age = item.age_seconds + sinceFetch;
    return { item, age, status: effectiveStatus(item, age, data?.interval_seconds ?? 15) };
  });
  const judged = items.filter((entry) => entry.status !== "unsupported");
  const problems = judged.filter((entry) => entry.status !== "healthy").length;
  const overall = items.length
    ? ((["unavailable", "degraded", "stale", "unknown"] as const).find((word) =>
        judged.some((entry) => entry.status === word),
      ) ?? "healthy")
    : "unknown";
  return (
    <>
      {header}
      {error && !data ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Skeleton label="Loading system health" />
      ) : (
        <>
          {error && (
            <p className="health-warning" role="alert">
              Health could not be refreshed. The figures below are from {formatAge(sinceFetch)}.
            </p>
          )}
          <section className={`health-overall health-overall--${overall}`} aria-label="Overall state">
            <StatusPill status={overall} />
            <p className="health-overall__text">{overallSentence(overall, problems)}</p>
            <p className="health-overall__time">Updated {formatAge(sinceFetch)}</p>
          </section>
          <div className="health-grid">
            {items.map(({ item, age, status }) => (
              <HealthCard key={item.key} item={item} status={status} ageSeconds={age} now={now} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
