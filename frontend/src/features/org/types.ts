/** Contracts in docs/API.md P4: names, roles and counts only, never content. */
export type Named = { id: string; name: string };
export type OrgUnit = {
  id: string;
  code: string | null;
  level: "group" | "division" | "section" | null;
  name: string;
  archived: boolean;
  parent_id: string | null;
  head: Named | null;
  acting_head: Named | null;
  stewards: Named[];
  people: number;
  members: number;
};
export type OrgSpace = {
  id: string;
  kind: "project" | "group";
  name: string;
  archived: boolean;
  stewards: Named[];
  members: number;
};
export type OrgTree = { units: OrgUnit[]; spaces: OrgSpace[] };
