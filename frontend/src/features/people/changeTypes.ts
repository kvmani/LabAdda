/** Reviewed staff changes (docs/API.md P2): server-built plans; clients never send steps. */
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type Role = "member" | "steward";

export type StaffFieldsDraft = {
  designation: string;
  employee_no: string;
  contact_email: string;
  contact_phone: string;
};
export type AddPersonRequest = {
  kind: "add_person";
  username: string;
  display_name: string;
  fields: Partial<StaffFieldsDraft>;
  home_unit_id: string;
  role: Role;
  joined_on?: string;
};
export type TransferRequest = {
  kind: "transfer";
  person_id: string;
  to_unit_id: string;
  role: Role;
  keep_previous: boolean;
  leave_workspace_ids: string[];
  acknowledge_no_steward: boolean;
};
export type ChangeRequest = AddPersonRequest | TransferRequest;

export type PlanStep = {
  target_type: "identity" | "workspace";
  target_id: string;
  summary: string;
  before: Record<string, JsonValue>;
  after: Record<string, JsonValue>;
};
export type PlanIssue = { code: string; message: string; target_id: string | null; count?: number | null };
export type ChangePlan = {
  kind: ChangeRequest["kind"];
  revisions: Record<string, number>;
  steps: PlanStep[];
  warnings: PlanIssue[];
  blockers: PlanIssue[];
  affected_people: number;
  digest: string;
};
export type ChangeReceipt = {
  applied: true;
  kind: ChangeRequest["kind"];
  person_id: string;
  revision: number;
  digest: string;
  activation?: { code: string; expires_at: string };
  stewards_notified?: number;
};
