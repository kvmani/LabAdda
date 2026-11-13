/** Console section keys mirror the current server policy, never workspace grants. */
export const SECTIONS = [
  { key: "overview", label: "Overview", path: "/admin" },
  { key: "people", label: "People", path: "/admin/people" },
  { key: "org", label: "Organisation", path: "/admin/org" },
  { key: "activity", label: "Activity", path: "/admin/activity" },
  { key: "health", label: "System health", path: "/admin/health" },
  { key: "storage", label: "Storage", path: "/admin/storage" },
  { key: "backups", label: "Backups", path: "/admin/backups" },
  { key: "audit", label: "Audit", path: "/admin/audit" },
  { key: "events", label: "Events", path: "/admin/events" },
  { key: "broadcast", label: "Broadcast", path: "/admin/broadcast" },
  { key: "settings", label: "Settings", path: "/admin/settings" },
  { key: "help", label: "Help for administrators", path: "/admin/help" },
] as const;
export type ConsoleSection = (typeof SECTIONS)[number]["key"];
export type ConsoleAccess = { sections: ConsoleSection[]; read_only: boolean; unit_admin: boolean };
