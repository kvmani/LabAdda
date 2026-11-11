import type { IconName, SelectOption, Tone } from "../../ui";
import type { EventSeverity, EventState } from "./types";

export const FILTER_KEYS = ["state", "severity", "component"] as const;

export const STATE_OPTIONS: SelectOption[] = [
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved", label: "Resolved" },
];
export const SEVERITY_OPTIONS: SelectOption[] = [
  { value: "info", label: "Information" },
  { value: "warning", label: "Warning" },
  { value: "error", label: "Error" },
  { value: "critical", label: "Critical" },
];
export const COMPONENT_OPTIONS: SelectOption[] = [
  { value: "application", label: "Application" },
  { value: "database", label: "Database" },
  { value: "file_storage", label: "File storage" },
  { value: "connections", label: "Live connections" },
  { value: "jobs", label: "Background jobs" },
  { value: "response_time", label: "Response time" },
  { value: "sign_in", label: "Sign-in" },
  { value: "backups", label: "Backups" },
  { value: "server", label: "Server" },
  { value: "certificate", label: "Certificate" },
];

const STATE_LABEL: Record<EventState, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

export const stateLabel = (state: EventState): string => STATE_LABEL[state];

export const severityPill: Record<EventSeverity, { tone: Tone; icon: IconName; label: string }> = {
  info: { tone: "info", icon: "info", label: "Information" },
  warning: { tone: "warn", icon: "warning", label: "Warning" },
  error: { tone: "danger", icon: "error", label: "Error" },
  critical: { tone: "danger", icon: "error", label: "Critical" },
};

export function eventsUrl(params: URLSearchParams): string {
  const query = new URLSearchParams();
  for (const key of [...FILTER_KEYS, "cursor"]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  const text = query.toString();
  return text ? `/admin/events?${text}` : "/admin/events";
}
