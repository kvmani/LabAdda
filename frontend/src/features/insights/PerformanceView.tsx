import { AreaChart, DataTable, EmptyState, LineChart, StatusPill, type Column } from "../../ui";
import {
  errorSeries,
  formatChange,
  formatCount,
  formatMs,
  formatRate,
  latencySeries,
  relative,
  trafficSeries,
} from "./model";
import type { Performance, PerfGroup } from "./types";

type Tile = { label: string; value: string; note: string; warn?: boolean };

function tiles(data: Performance): Tile[] {
  const now = data.current;
  const before = data.previous;
  if (!now) return [];
  const limit = data.limits;
  return [
    {
      label: "Requests",
      value: formatCount(now.requests),
      note: formatChange(relative(now.requests, before?.requests ?? null)),
    },
    {
      label: "Slowest 5 % of requests (p95)",
      value: formatMs(now.p95_ms),
      note: `Target under ${limit.p95_ms} ms. ${formatChange(relative(now.p95_ms, before?.p95_ms ?? null))}`,
      warn: now.p95_ms !== null && now.p95_ms > limit.p95_ms,
    },
    {
      label: "Median response (p50)",
      value: formatMs(now.p50_ms),
      note: formatChange(relative(now.p50_ms, before?.p50_ms ?? null)),
    },
    {
      label: "Server errors",
      value: formatRate(now.error_rate),
      note: `${formatCount(now.errors)} failed. Target under ${formatRate(limit.error_rate)}`,
      warn: now.error_rate !== null && now.error_rate > limit.error_rate,
    },
    {
      label: "Failed sign-ins",
      value: formatRate(now.signin_failure_rate),
      note: `${formatCount(now.signin_failed)} of ${formatCount(now.signin_ok + now.signin_failed)} attempts`,
    },
    {
      label: "Peak live connections",
      value: formatCount(now.peak_connections),
      note: formatChange(relative(now.peak_connections, before?.peak_connections ?? null)),
    },
  ];
}

const COLUMNS: Column<PerfGroup>[] = [
  { key: "label", header: "Feature area", render: (row) => row.label, sortValue: (row) => row.label },
  { key: "status", header: "State", render: (row) => <StatusPill status={row.status} /> },
  {
    key: "requests",
    header: "Requests",
    align: "end",
    render: (row) => formatCount(row.requests),
    sortValue: (row) => row.requests,
  },
  {
    key: "p95",
    header: "p95",
    align: "end",
    render: (row) => formatMs(row.p95_ms),
    sortValue: (row) => row.p95_ms ?? -1,
  },
  {
    key: "p95_change",
    header: "p95 change",
    render: (row) => formatChange(relative(row.p95_ms, row.previous_p95_ms)),
    sortValue: (row) => relative(row.p95_ms, row.previous_p95_ms) ?? -Infinity,
  },
  {
    key: "p50",
    header: "Median",
    align: "end",
    render: (row) => formatMs(row.p50_ms),
    sortValue: (row) => row.p50_ms ?? -1,
  },
  {
    key: "errors",
    header: "Server errors",
    align: "end",
    render: (row) => `${formatCount(row.errors)} (${formatRate(row.error_rate)})`,
    sortValue: (row) => row.errors,
  },
];

export function PerformanceView({
  data,
  period,
  updated,
}: {
  data: Performance;
  period: string;
  updated?: string;
}) {
  if (data.state === "unknown" || !data.current)
    return (
      <EmptyState title="Not measured yet">
        <p>
          No requests were recorded in this period. Figures appear a few minutes after people use LabAdda.
        </p>
      </EmptyState>
    );
  return (
    <div className="insights-stack">
      <StatusPill status={data.current.status} />
      <ul className="insights-tiles" aria-label="Performance figures">
        {tiles(data).map((tile) => (
          <li key={tile.label} className={`insights-tile${tile.warn ? " insights-tile--warn" : ""}`}>
            <p className="insights-tile__label">{tile.label}</p>
            <p className="insights-tile__value">{tile.value}</p>
            <p className="insights-muted">{tile.note}</p>
          </li>
        ))}
      </ul>
      <div className="insights-charts">
        <LineChart
          title="Response time"
          series={latencySeries(data.points)}
          unit="ms"
          period={period}
          updated={updated}
        />
        <LineChart
          title="Requests ending in a server error"
          series={errorSeries(data.points)}
          unit="%"
          period={period}
          updated={updated}
        />
        <AreaChart
          title="Requests"
          series={trafficSeries(data.points)}
          unit="requests"
          period={period}
          updated={updated}
        />
      </div>
      <DataTable
        caption="Feature areas, slowest first"
        columns={COLUMNS}
        rows={data.groups}
        rowKey={(row) => row.key}
        initialSort={{ key: "p95", direction: "descending" }}
        empty={{ title: "No requests in this period" }}
      />
    </div>
  );
}
