import type { SelectOption } from "../../ui";
import type { PersonOption } from "./types";

export const FILTER_KEYS = ["start", "end", "actor_id", "person_id", "unit_id", "group", "outcome", "q"];
export const GROUP_OPTIONS: SelectOption[] = [
  { value: "people", label: "People" },
  { value: "access", label: "Access" },
  { value: "organisation", label: "Organisation" },
  { value: "authority", label: "Authority" },
  { value: "sign_in", label: "Sign-in security" },
  { value: "settings", label: "Settings and storage" },
  { value: "exports", label: "Exports" },
];
export const OUTCOME_OPTIONS: SelectOption[] = [
  { value: "success", label: "Succeeded" },
  { value: "denied", label: "Refused" },
  { value: "failed", label: "Failed" },
];

/** Keep the open record out of list requests and paging out of report requests. */
export function auditUrl(params: URLSearchParams, report = false): string {
  const query = new URLSearchParams();
  for (const key of [...FILTER_KEYS, ...(report ? [] : ["cursor"])]) {
    const value = params.get(key);
    if (value) query.set(key, value);
  }
  return `/admin/audit${report ? "/export.csv" : ""}${query.size ? "?" + query.toString() : ""}`;
}

export function personOptions(people: PersonOption[]): SelectOption[] {
  return people.map((person) => ({
    value: person.id,
    label: `${person.display_name} (${person.username})`,
  }));
}

export function outcomeLabel(outcome: string): string {
  return OUTCOME_OPTIONS.find((item) => item.value === outcome)?.label ?? outcome;
}

/** Recorded values are shown as plain text; structured values are summarised, never raw JSON. */
export function showValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

export function fieldLabel(field: string): string {
  const text = field.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
