let siteTimeZone: string | undefined = "Asia/Kolkata";

/** Set from the signed-in session so every screen shows times in the site time zone. */
export function setSiteTimeZone(tz: string | undefined) {
  siteTimeZone = tz || "Asia/Kolkata";
}

export function fmtTime(iso: string | null | undefined, tz: string | undefined = siteTimeZone || "Asia/Kolkata"): string {
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

/** Formats clock time in IST / 12-hour format e.g. "7:55 pm", "11:28 am" */
export function fmtClockTimeIST(iso: string | null | undefined, tz = siteTimeZone || "Asia/Kolkata"): string {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat("en-IN", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: tz,
    }).format(new Date(iso)).toLowerCase();
  } catch {
    return "";
  }
}

/** Formats date badge separator e.g. "Today", "Yesterday", "Friday", or "15 Nov 2026" */
export function fmtDateBadgeIST(iso: string | null | undefined, tz = siteTimeZone || "Asia/Kolkata"): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const fmtOptions: Intl.DateTimeFormatOptions = { timeZone: tz, year: "numeric", month: "numeric", day: "numeric" };
  try {
    const dStr = new Intl.DateTimeFormat("en-IN", fmtOptions).format(d);
    const nowStr = new Intl.DateTimeFormat("en-IN", fmtOptions).format(now);
    const yesterday = new Date(now.getTime() - 86400000);
    const yStr = new Intl.DateTimeFormat("en-IN", fmtOptions).format(yesterday);

    if (dStr === nowStr) return "Today";
    if (dStr === yStr) return "Yesterday";

    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
    if (diffDays >= 0 && diffDays < 7) {
      return new Intl.DateTimeFormat("en-IN", { weekday: "long", timeZone: tz }).format(d);
    }
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: tz,
    }).format(d);
  } catch {
    return d.toDateString();
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
