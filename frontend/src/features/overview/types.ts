import type { HealthStatus } from "../../ui";

export type Severity = "critical" | "error" | "warning" | "info";

export type AttentionEntry = {
  id: string;
  kind: "health" | "event" | "people";
  severity: Severity;
  status: HealthStatus | null;
  title: string;
  detail: string;
  route: string;
  help: string | null;
  at: string | null;
};

export type TileState = "measured" | "unknown" | "stale" | "suppressed" | HealthStatus;

export type OverviewTile = {
  key: string;
  label: string;
  unit: "people" | "connections" | "bytes" | "seconds" | "events";
  link: string;
  state: TileState;
  value: number | null;
  trend: (number | null)[] | null;
  updated_at: string | null;
  finished_at?: string | null;
  by_severity?: Record<Severity, number>;
};

export type DayPoint = { day: string; state: string; value: number | null };

export type Overview = {
  generated_at: string;
  timezone: string;
  period: { first_day: string; last_day: string };
  overall: HealthStatus;
  attention: AttentionEntry[];
  tiles: OverviewTile[];
  charts: {
    activity: { state: string; points: DayPoint[] };
    response_time: { state: string; unit: string; points: DayPoint[] };
  };
};
