/** Responses of GET /admin/analytics/summary and /units (docs/API.md, A5). */
export type Period = "7d" | "30d" | "90d" | "12m";

export type DayRange = { first_day: string; last_day: string };

export type Tile = {
  key: "active_day" | "active_week" | "active_month" | "active_share" | "peak_connections" | "items_created";
  label: string;
  unit: "people" | "fraction" | "connections" | "items";
  state: "measured" | "unknown";
  value: number | null;
  previous: number | null;
  active?: number | null;
  accounts?: number;
};

export type FeaturePoint = { start: string; values: Record<string, number> | null };

export type SummaryCharts = {
  active_per_day: { day: string; value: number | null }[];
  features: {
    bucket: "day" | "week" | "month";
    series: { key: string; label: string }[];
    points: FeaturePoint[];
  };
  items_by_kind: { key: "org" | "project" | "group"; label: string; value: number }[];
  weekday_hour: {
    state: "measured" | "unknown";
    from: string | null;
    cells: { weekday: number; hour: number; value: number }[];
  };
  storage: { day: string; files_bytes: number | null; database_bytes: number | null }[];
  upload_sizes: { key: string; label: string; value: number }[];
};

type Common = {
  period: Period;
  timezone: string;
  generated_at: string;
  current: DayRange;
  previous: DayRange;
};

export type Summary = Common &
  (
    | { state: "unknown"; tiles: []; charts: null }
    | { state: "measured"; tiles: Tile[]; charts: SummaryCharts }
  );

export type Figure = { state: "shown"; value: number } | { state: "suppressed" } | { state: "unknown" };

export type UnitRow = {
  id: string;
  name: string;
  parent_id: string | null;
  archived: boolean;
  active_people: Figure;
  items_created: Figure | null;
  previous_active_people: Figure | null;
};

export type Units = Common & {
  minimum_group: number;
  rounded_to: number;
  state: "measured" | "unknown";
  units: UnitRow[];
  no_home_unit: Omit<UnitRow, "id" | "name" | "parent_id" | "archived"> | null;
  chart: { label: string; value: number }[];
};
