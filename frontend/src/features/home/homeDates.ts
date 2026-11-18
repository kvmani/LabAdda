/** Site-local day boundaries preserve whole calendar days across Windows and DST. */
export function siteDay(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
function midnight(day: string, timezone: string): Date {
  const target = Date.parse(`${day}T00:00:00Z`);
  let instant = target;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let pass = 0; pass < 2; pass++) {
    const parts: Record<string, number> = {};
    formatter.formatToParts(new Date(instant)).forEach((part) => {
      if (part.type !== "literal") parts[part.type] = Number(part.value);
    });
    const observed = Date.UTC(
      parts.year ?? 0,
      (parts.month ?? 1) - 1,
      parts.day ?? 1,
      parts.hour ?? 0,
      parts.minute ?? 0,
      parts.second ?? 0,
    );
    instant += target - observed;
  }
  return new Date(instant);
}
export function dayRange(day: string, timezone: string): { start: string; end: string } {
  const next = new Date(`${day}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return {
    start: midnight(day, timezone).toISOString(),
    end: midnight(next.toISOString().slice(0, 10), timezone).toISOString(),
  };
}
