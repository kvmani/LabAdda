import { useEffect, useMemo, useState } from "react";
import { LineChart } from "../../ui";
import { usePolledData } from "../admin/usePolledData";
import { chartPoints, formatAge, scaleValues } from "./model";
import type { ChartSpec, SeriesResponse } from "./types";

const REFRESH_MS = 60_000;

function useMinute(): number {
  const [minute, setMinute] = useState(() => Math.floor(Date.now() / REFRESH_MS));
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") setMinute(Math.floor(Date.now() / REFRESH_MS));
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);
  return minute;
}

/** The last 24 hours of one stored series, a point per minute; missing minutes are gaps (AD-08). */
export function HealthChart({ label, spec, now }: { label: string; spec: ChartSpec; now: number }) {
  const minute = useMinute();
  const path = useMemo(() => {
    const end = minute * REFRESH_MS;
    const query = new URLSearchParams({
      metric: spec.metric,
      dimension: spec.dimension,
      resolution: "minute",
      from: new Date(end - 24 * 3_600_000).toISOString(),
      to: new Date(end + REFRESH_MS).toISOString(),
    });
    return `/admin/metrics/series?${query.toString()}`;
  }, [minute, spec.metric, spec.dimension]);
  const { data, fetchedAt, error } = usePolledData<SeriesResponse>(path, 0);
  const series = useMemo(() => {
    const rows = data?.points ?? [];
    const { factor, unit } = scaleValues(
      rows.map((row) => row.value),
      spec.unit,
    );
    return { unit, points: chartPoints(rows, factor) };
  }, [data, spec.unit]);
  if (error && !data) return <p role="status">The 24-hour chart could not be loaded.</p>;
  if (!data) return <p role="status">Loading the 24-hour chart…</p>;
  return (
    <LineChart
      title={`${label}, last 24 hours`}
      period="Last 24 hours"
      updated={fetchedAt ? `Updated ${formatAge((now - fetchedAt) / 1000)}` : undefined}
      unit={series.unit}
      series={[{ label, points: series.points }]}
      height={160}
    />
  );
}
