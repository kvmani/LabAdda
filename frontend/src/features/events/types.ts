export type EventState = "open" | "acknowledged" | "resolved";
export type EventSeverity = "info" | "warning" | "error" | "critical";

export type OpsEvent = {
  id: number;
  code: string;
  component: string;
  component_label: string;
  severity: EventSeverity;
  summary: string;
  detail: Record<string, unknown>;
  first_at: string;
  last_at: string;
  count: number;
  state: EventState;
  acknowledged_by: { id: string; display_name: string } | null;
  acknowledged_at: string | null;
  note: string | null;
  resolved_at: string | null;
  help: string | null;
};

export type EventPage = { events: OpsEvent[]; next_cursor: string | null };
