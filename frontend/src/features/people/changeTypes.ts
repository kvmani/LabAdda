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
export type PositionKind = "head" | "deputy";
export type PromoteRequest = {
  kind: "promote";
  person_id: string;
  designation?: string | null;
  workspace_id?: string;
  role?: Role;
  position?: PositionKind;
};
export type ChangeAuthorityRequest = {
  kind: "change_authority";
  workspace_id: string;
  position: PositionKind;
  successor_id: string;
  acting: boolean;
  ends_on?: string;
  outgoing_role: Role;
};
export type AdditionalChargeRequest = {
  kind: "additional_charge";
  person_id: string;
  workspace_id: string;
  role: Role;
  position?: PositionKind;
  ends_on?: string;
};
export type LeaveRequest = {
  kind: "leave";
  person_id: string;
  expected_return_on: string;
  block_sign_in: boolean;
  acting: { position_id: string; successor_id: string }[];
};
export type SuccessorChoice = {
  workspace_id: string;
  successor_id: string;
  acting?: boolean;
  ends_on?: string;
};
export type RetireRequest = {
  kind: "retire";
  person_id: string;
  status: "retired" | "left";
  keep_workspace_ids: string[];
  successors: SuccessorChoice[];
  acknowledge_no_steward: boolean;
};
export type PersonOnlyRequest = { kind: "return" | "suspend" | "reinstate"; person_id: string };
export type ChangeRequest =
  | AddPersonRequest
  | TransferRequest
  | PromoteRequest
  | ChangeAuthorityRequest
  | AdditionalChargeRequest
  | LeaveRequest
  | RetireRequest
  | PersonOnlyRequest;
export type Candidates = {
  workspace: { id: string; name: string; kind: string };
  people: { id: string; display_name: string; username: string; role: Role | null }[];
  truncated: boolean;
};

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
