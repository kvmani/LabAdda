import type { OrgUnit } from "./types";

/** The unit's level in plain words; units made before levels existed are just "Unit". */
export function levelWord(unit: OrgUnit): string {
  if (unit.level) return unit.level.charAt(0).toUpperCase() + unit.level.slice(1);
  return unit.parent_id ? "Unit" : "Organisation";
}
