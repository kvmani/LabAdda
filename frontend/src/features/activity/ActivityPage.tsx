import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BASE } from "../../config";
import { EmptyState, ErrorState, PageHeader, Select, Skeleton } from "../../ui";
import { formatAge } from "../health/model";
import { useNow, usePolledData } from "../admin/usePolledData";
import { ActivityCharts } from "./ActivityCharts";
import { ActivityTiles } from "./ActivityTiles";
import { ExportActivity } from "./ExportActivity";
import { UnitActivity } from "./UnitActivity";
import { PERIODS, parsePeriod, periodLabel, rangeText } from "./model";
import type { Period, Summary, Units } from "./types";
import "./activity.css";

const REFRESH_MS = 60_000;

/** Usage analytics (AD-08): site totals, and per-unit figures protected on the server. */
export function ActivityPage() {
  const [params, setParams] = useSearchParams();
  const period = parsePeriod(params.get("period"));
  const [denied, setDenied] = useState(false);
  const onDenied = useCallback(() => setDenied(true), []);
  const summary = usePolledData<Summary>(`/admin/analytics/summary?period=${period}`, REFRESH_MS, onDenied);
  const units = usePolledData<Units>(`/admin/analytics/units?period=${period}`, REFRESH_MS, onDenied);
  const now = useNow(10_000);
  const choose = (value: string) => {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set("period", parsePeriod(value));
      return next;
    });
  };
  const header = (
    <PageHeader
      title="Activity"
      scope="How much LabAdda is used. Counts and sizes only; nobody's messages, notes or files are shown."
      helpHref={`${BASE}/help/admin/activity-page`}
      action={denied ? undefined : <ExportActivity period={period} onDenied={onDenied} />}
    />
  );
  if (denied)
    return (
      <>
        {header}
        <ErrorState
          title="Your administration access changed"
          message="Usage figures have been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );
  return (
    <>
      {header}
      <div className="activity-controls">
        <Select
          label="Period"
          value={period}
          options={PERIODS}
          onChange={(event) => choose(event.target.value)}
        />
      </div>
      <ActivityBody
        period={period}
        summary={summary.data}
        units={units.data}
        error={summary.error || units.error}
        updated={
          summary.fetchedAt === null ? undefined : `Updated ${formatAge((now - summary.fetchedAt) / 1000)}`
        }
        reload={() => {
          summary.reload();
          units.reload();
        }}
      />
    </>
  );
}

type BodyProps = {
  period: Period;
  summary: Summary | null;
  units: Units | null;
  error: string;
  updated?: string;
  reload: () => void;
};

function ActivityBody({ period, summary, units, error, updated, reload }: BodyProps) {
  if (error && (!summary || !units)) return <ErrorState message={error} onRetry={reload} />;
  if (!summary || !units) return <Skeleton label="Loading usage figures" />;
  if (summary.state === "unknown")
    return (
      <EmptyState title="Not measured yet">
        No usage has been recorded for the {periodLabel(period).toLowerCase()}. Figures appear once people
        sign in and the server has collected them for a few minutes. This is not the same as no use.
      </EmptyState>
    );
  const range = `${periodLabel(period)} (${rangeText(summary.current)})`;
  return (
    <>
      {error && (
        <p className="activity-warning" role="alert">
          The figures could not be refreshed. Those below are from the last successful update.
        </p>
      )}
      <p className="activity-note">
        Compared with the previous period, {rangeText(summary.previous)}. Days are counted in the site time
        zone ({summary.timezone}).
      </p>
      <ActivityTiles tiles={summary.tiles} period={range} />
      <ActivityCharts charts={summary.charts} period={range} updated={updated} />
      <UnitActivity units={units} period={range} updated={updated} />
    </>
  );
}
