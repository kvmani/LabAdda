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

export type CockpitKPIs = {
  total_accounts: number;
  active_accounts: number;
  adoption_rate: number;
  total_workspaces: number;
  workspaces_by_kind: Record<string, number>;
  total_collaboration_items: number | null;
  collaboration_state?: string;
  total_storage_bytes: number;
  total_storage_formatted: string;
  open_events_count: number;
  events_by_severity: Record<string, number>;
};

export type PopularWorkspace = {
  id: string;
  name: string;
  kind: string;
  active_people: number;
  has_steward: boolean;
  total_items: number;
};

export type StorageConsumer = {
  id: string;
  name: string;
  kind: string;
  bytes: number;
  formatted: string;
};

export type ReliabilityEvent = {
  id: string;
  code: string;
  component: string;
  severity: string;
  summary: string;
  first_at: string;
  last_at: string;
  recommendation: string;
};

export type Bottlenecks = {
  storage: {
    top_workspaces: StorageConsumer[];
    headroom_status: string;
  };
  governance: {
    unstaffed_units_count: number;
    unstaffed_units: string[];
    unstaffed_projects_count: number;
    unstaffed_projects: string[];
  };
  performance: {
    p95_latency_ms: number | null;
    latency_status: string;
  };
  reliability: {
    open_events: ReliabilityEvent[];
    critical_count: number;
    warning_count: number;
  };
};

export type UsagePattern = {
  feature: string;
  count: number;
  percentage: number;
  icon: string;
  role: string;
};

export type CockpitData = {
  generated_at: string;
  timezone: string;
  kpis: CockpitKPIs;
  popular_workspaces: PopularWorkspace[];
  bottlenecks: Bottlenecks;
  usage_patterns: {
    feature_distribution: UsagePattern[];
    peak_summary: string;
  };
};

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
  cockpit?: CockpitData;
};
