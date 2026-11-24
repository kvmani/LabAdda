/** Responses of GET /admin/insights/trends and /admin/insights/performance (docs/API.md). */
export type FigureState = "measured" | "suppressed" | "unknown";

export type Trend = "growing" | "new" | "core" | "steady" | "declining" | "dormant" | "unused" | "unknown";

export type WeekPoint = {
  start: string;
  partial: boolean;
  state: FigureState;
  active_people: number | null;
  values: Record<string, number> | null;
};

export type FeatureMomentum = {
  key: string;
  label: string;
  trend: Trend;
  advice: string;
  weekly_recent: number | null;
  weekly_prior: number | null;
  change: number | null;
  share: number | null;
  per_person: number | null;
  sparkline: (number | null)[];
};

export type PeopleTrend = {
  accounts: number;
  weekly_recent: number | null;
  weekly_prior: number | null;
  change: number | null;
  reach: number | null;
  stickiness: number | null;
  trend: Trend;
};

export type Trends = {
  weeks: number;
  timezone: string;
  generated_at: string;
  first_day: string;
  last_day: string;
  compare_weeks: number;
  state: FigureState;
  series: { key: string; label: string }[];
  points: WeekPoint[];
  features: FeatureMomentum[];
  people: PeopleTrend | null;
};

export type Span = "24h" | "7d" | "30d" | "90d";

export type PerfFigures = {
  requests: number;
  errors: number;
  error_rate: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
};

export type PerfSummary = PerfFigures & {
  status: "healthy" | "degraded" | "unknown";
  signin_ok: number;
  signin_failed: number;
  signin_failure_rate: number | null;
  peak_connections: number | null;
};

export type PerfPoint = PerfFigures & {
  start: string;
  signin_failed: number | null;
  peak_connections: number | null;
};

export type PerfGroup = PerfFigures & {
  key: string;
  label: string;
  previous_p95_ms: number | null;
  previous_requests: number;
  status: "healthy" | "degraded" | "unknown";
};

export type Performance = {
  span: Span;
  bucket: "hour" | "day";
  timezone: string;
  generated_at: string;
  from: string;
  to: string;
  limits: { p95_ms: number; error_rate: number };
  state: "measured" | "unknown";
  current: PerfSummary | null;
  previous: PerfSummary | null;
  points: PerfPoint[];
  groups: PerfGroup[];
};
