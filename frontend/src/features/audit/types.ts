/** Audit metadata contract (docs/API.md A2); never message, note or file content. */
export type AuditChange = { field: string; before: string | null; after: string | null };
export type AuditEvent = {
  id: number;
  created_at: string;
  action: string;
  group: string;
  group_label: string;
  sentence: string;
  outcome: string;
  reason: string | null;
  actor: { id: string; display_name: string } | null;
  target: { id: string; display_name: string } | null;
  unit: { id: string; name: string; kind: string } | null;
  changes: AuditChange[];
  detail: Record<string, unknown>;
};
export type AuditPage = { events: AuditEvent[]; next_cursor: string | null };
export type PersonOption = { id: string; display_name: string; username: string };
