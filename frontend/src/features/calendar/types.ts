export type CalendarScopeKind = "site" | "workspace" | "personal";

export type CalendarSource = {
  id: string;
  title: string;
  kind: string;
  level?: string | null;
  color: string;
  can_write: boolean;
  inherited?: boolean;
};

export type CalendarEvent = {
  revision: number;
  id: string;
  scope_kind: CalendarScopeKind;
  workspace_id: string | null;
  workspace_name?: string | null;
  owner_id: string | null;
  created_by: string;
  creator_name?: string | null;
  title: string;
  description?: string | null;
  location?: string | null;
  starts_at: string;
  ends_at: string;
  all_day: boolean;
  color?: string | null;
  created_at: string;
  updated_at: string;
  can_edit: boolean;
  can_delete: boolean;
};

export type CalendarViewMode = "month" | "week" | "day" | "agenda";

export type EventFormData = {
  revision?: number;
  id?: string;
  scope_kind: CalendarScopeKind;
  workspace_id: string;
  title: string;
  description: string;
  location: string;
  start_date: string;
  start_time: string;
  end_date: string;
  end_time: string;
  all_day: boolean;
  color: string;
};
