import type { HealthStatus } from "../../ui";

export type ChartSpec = { metric: string; dimension: string; unit: string };

export type HealthItem = {
  key: string;
  label: string;
  status: HealthStatus;
  value: number | string | null;
  unit: string;
  detail: string;
  checked_at: string;
  age_seconds: number;
  help: string;
  chart: ChartSpec | null;
};

export type HealthReport = {
  overall: HealthStatus;
  generated_at: string;
  interval_seconds: number;
  items: HealthItem[];
};

export type SeriesResponse = {
  unit: string;
  points: { bucket_start: string; value: number; samples: number }[];
};
