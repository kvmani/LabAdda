export function fmtTime(iso: string | null | undefined, tz?: string): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: tz,
    }).format(new Date(iso));
  } catch {
    return new Date(iso).toLocaleString();
  }
}

/** Convert a datetime-local input value to an ISO string with offset. */
export function localToIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d.toISOString();
}

export function isoToLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function kindLabel(kind: string): string {
  return kind === "group" ? "Group" : kind === "project" ? "Project" : "Unit";
}

export function fmtBytes(value: number | null): string {
  if (value === null || !Number.isFinite(value) || value < 0) return "Unknown";
  const units = ["B", "KiB", "MiB", "GiB"];
  const scale = value === 0 ? 0 : Math.min(3, Math.floor(Math.log(value) / Math.log(1024)));
  return `${(value / 1024 ** scale).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${units[scale]}`;
}
