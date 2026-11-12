import type { SelectOption } from "../../ui";
import type { HeldPosition, Unit } from "./types";

export const FILTER_KEYS = ["q", "status", "unit_id", "include_children", "role", "sort", "descending"];
export const STATUS_OPTIONS = [
  { value: "invited", label: "Invited" },
  { value: "active", label: "Active" },
  { value: "on_leave", label: "On leave" },
  { value: "suspended", label: "Suspended" },
  { value: "retired", label: "Retired" },
  { value: "left", label: "Left" },
];

/** Keep profile tabs out of list requests and pagination out of report requests. */
export function peopleUrl(params: URLSearchParams, report = false): string {
  const query = new URLSearchParams();
  for (const key of [...FILTER_KEYS, ...(report ? [] : ["cursor"])]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  return `/admin/people${report ? "/export.csv" : ""}${query.size ? "?" + query.toString() : ""}`;
}

/** Calendar dates are already site-local; never shift them into the browser's zone. */
export function calendarDate(value: string | null): string {
  if (!value) return "Not recorded";
  const instant = new Date(value + "T00:00:00Z");
  if (!Number.isFinite(instant.getTime()) || instant.toISOString().slice(0, 10) !== value)
    return "Unknown date";
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(instant);
}

/** Full unit paths disambiguate identically named sections without displaying IDs. */
export function unitOptions(units: Unit[]): SelectOption[] {
  const organisations = units.filter((unit) => unit.kind === "org");
  const byId = new Map(organisations.map((unit) => [unit.id, unit]));
  return organisations
    .map((unit) => {
      const path = [unit.name];
      const seen = new Set([unit.id]);
      let parent = unit.parent_id;
      while (parent && !seen.has(parent)) {
        seen.add(parent);
        const ancestor = byId.get(parent);
        if (!ancestor) break;
        path.unshift(ancestor.name);
        parent = ancestor.parent_id;
      }
      return { value: unit.id, label: path.join(" / ") };
    })
    .sort((left, right) => left.label.localeCompare(right.label));
}

/** Units a person can be placed in: open organisation units, still named by their full path. */
export function openUnitOptions(units: Unit[], exclude?: string | null): SelectOption[] {
  const closed = new Set(units.filter((unit) => unit.archived).map((unit) => unit.id));
  return unitOptions(units).filter((option) => !closed.has(option.value) && option.value !== exclude);
}

const POSITION_WORDS = { head: "Head", deputy: "Deputy", charge: "Additional charge" } as const;

/** "Acting Head of Thin Films Section until 11 Jan 2027" — names and dates only. */
export function positionLabel(item: HeldPosition): string {
  const word = POSITION_WORDS[item.position];
  const title = item.acting ? `Acting ${word}` : word;
  const until = item.ends_on ? ` until ${calendarDate(item.ends_on)}` : "";
  return `${title} ${item.position === "charge" ? "in" : "of"} ${item.workspace.name}${until}`;
}
