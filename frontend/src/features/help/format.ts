const UPDATED = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** Formats a front matter date such as 2026-11-11 as "11 Nov 2026". */
export function formatUpdated(date: string): string {
  return UPDATED.format(new Date(`${date}T00:00:00Z`));
}
