/** Metadata contracts in docs/API.md P1; no collaboration-content fields. */
export type StaffStatus = "invited" | "active" | "on_leave" | "suspended" | "retired" | "left";
export type HeldPosition = {
  id: string;
  workspace: { id: string; name: string };
  position: "head" | "deputy" | "charge";
  acting: boolean;
  starts_on: string;
  ends_on: string | null;
};
export type Person = {
  id: string;
  username: string;
  display_name: string;
  employee_no: string | null;
  designation: string | null;
  status: StaffStatus;
  revision: number;
  is_admin: boolean;
  sign_in_enabled: boolean;
  home_unit: { id: string; name: string; level?: UnitLevel } | null;
  last_seen_on: string | null;
  positions: HeldPosition[];
};
export type StaffRecord = Person & {
  contact_email: string | null;
  contact_phone: string | null;
  extension: string | null;
  residence_phone: string | null;
  status_effective_on: string | null;
  expected_return_on: string | null;
  joined_on: string | null;
};
export type Directory = { people: Person[]; next_cursor: string | null };
export type UnitLevel = "group" | "division" | "section" | null;
export type Unit = {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  archived?: boolean;
  level?: UnitLevel;
};
export type AccessPage = {
  memberships: {
    workspace: { id: string; name: string; kind: string; archived: boolean };
    role: string;
    inherited: boolean;
    sign_in_enabled: boolean;
  }[];
  next_cursor: string | null;
};
export type TimelinePage = {
  items: {
    id: number;
    occurred_on: string;
    actor: { id: string; display_name: string } | null;
    summary: string;
    reason: string | null;
    outcome: string;
  }[];
  next_cursor: number | null;
};
