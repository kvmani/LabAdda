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
export type UnitCreateRequest = {
  kind: "unit_create";
  parent_id: string;
  name: string;
  code: string;
  head_id?: string;
};
export type UnitRenameRequest = { kind: "unit_rename"; unit_id: string; name?: string; code?: string };
export type UnitMoveRequest = { kind: "unit_move"; unit_id: string; new_parent_id: string };
export type UnitMergeRequest = { kind: "unit_merge"; unit_id: string; into_unit_id: string };
export type UnitSplitRequest = {
  kind: "unit_split";
  unit_id: string;
  name: string;
  code: string;
  person_ids: string[];
  acknowledge_no_steward: boolean;
};
export type UnitOnlyRequest = { kind: "unit_close" | "unit_reopen"; unit_id: string };
export type PersonOnlyRequest = { kind: "return" | "suspend" | "reinstate"; person_id: string };
export type ChangeRequest =
  | AddPersonRequest
  | TransferRequest
  | PromoteRequest
  | ChangeAuthorityRequest
  | AdditionalChargeRequest
  | LeaveRequest
  | RetireRequest
  | PersonOnlyRequest
  | UnitCreateRequest
  | UnitRenameRequest
  | UnitMoveRequest
  | UnitMergeRequest
  | UnitSplitRequest
  | UnitOnlyRequest;
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
  kind: ChangeRequest["kind"] | "bulk";
  revisions: Record<string, number>;
  steps: PlanStep[];
  warnings: PlanIssue[];
  blockers: PlanIssue[];
  affected_people: number;
  digest: string;
};
export type ChangeReceipt = {
  /** Present instead of `applied` when the change was stored for a later day (PO-06). */
  scheduled?: true;
  effective_on?: string;
  applied?: true;
  kind: ChangeRequest["kind"];
  /** Staff changes name the person; unit changes name the unit instead. */
  person_id?: string;
  unit_id?: string;
  revision?: number;
  digest: string;
  activation?: { code: string; expires_at: string };
  stewards_notified?: number;
};

/** Staff list import and bulk changes (docs/API.md P6). */
export type BulkItem =
  | AddPersonRequest
  | { kind: "transfer"; person_id: string; to_unit_id: string; role: Role }
  | { kind: "suspend"; person_id: string }
  | { kind: "edit_person"; person_id: string; fields: Record<string, string | null> };
export type ImportRow = {
  line: number;
  group: "add" | "change" | "transfer" | "errors";
  username: string;
  display_name: string | null;
  summary: string[];
  errors: string[];
  warnings: string[];
  requests: BulkItem[];
};
export type ImportReport = {
  rows: ImportRow[];
  counts: { add: number; change: number; transfer: number; errors: number; unchanged: number };
  absent: { username: string; display_name: string }[];
  absent_total: number;
  digest: string;
};
export type BulkReceipt = {
  applied: true;
  kind: "bulk";
  digest: string;
  count: number;
  added: {
    person_id: string;
    username: string;
    display_name: string;
    activation: { code: string; expires_at: string };
  }[];
};

/** A change waiting for its day or for review (docs/API.md P5). */
export type ScheduledItem = {
  id: string;
  kind: ChangeRequest["kind"];
  effective_on: string;
  state: "pending" | "needs_review";
  note: string | null;
  reason: string;
  subject_id: string | null;
  steps: string[];
  created_by: string;
  created_at: string;
};
export type AttentionItem = {
  id: string;
  severity: "critical" | "error" | "warning" | "info";
  title: string;
  detail: string;
  route: string;
};
