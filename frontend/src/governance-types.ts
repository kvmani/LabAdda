export type OriginalMeasurement = {
  state: 'partial'; source: 'asset_metadata'; observed_at: string; tracked_files: number;
  pending_upload_original_bytes: number; tracked_original_bytes: number; provisional_original_bytes: number; committed_original_bytes: number;
  tracked_preview_bytes?: number; unknown_preview_files?: number;
  unmeasured: string[]; complete_for_enforcement: false;
};
export type ChargeBucket = {live_bytes: number; live_items: number; removed_bytes: number; removed_items: number};
export type LogicalCharges = {
  methods: {text: string; board: string};
  by_type: {post: ChargeBucket; chat: ChargeBucket; note?: ChargeBucket; board_object: ChargeBucket};
  live_logical_bytes: number; removed_logical_bytes: number;
  board_charges: 'complete' | 'incomplete'; unreconciled_boards: number | null;
  observed_at: string; complete_for_enforcement: false;
};
export type UserUsage = {
  measurement: OriginalMeasurement;
  logical_charges?: LogicalCharges;
  runtime_limit: {bytes: number; source: string; policy_proposals_enforced: false};
};
export type WorkspaceUsage = {
  scope: 'workspace'; workspace_id: string; observed_at: string;
  files: {
    retained_files: number; retained_original_bytes: number; recorded_preview_bytes: number;
    unknown_preview_files: number; removed_post_original_bytes: number; pending_upload_bytes: null;
  };
  logical_charges: LogicalCharges;
  workspace_budget: {bytes: null; state: 'not_configured'; policy_proposals_enforced: false};
  complete_for_enforcement: false;
};
export type DatabaseStorage = {
  state: 'ready' | 'unknown'; observed_at: string; database_bytes: number | null; other_bytes: number | null;
  categories: Record<'collaboration_text' | 'personal_notes' | 'board_history' | 'file_metadata' | 'identity_and_access' | 'audit_and_governance', number | null>;
  board_history: {retained_operations: number | null; snapshots: number | null};
};
export type SiteUsage = {
  assets: OriginalMeasurement;
  logical_charges?: LogicalCharges;
  database?: DatabaseStorage;
  filesystem: {state: string; free_bytes: number | null; total_bytes: number | null; free_inodes: number | null};
};
export type ProposedProfile = {
  schema_version: number; mode: 'observation'; max_attachment_bytes: number;
  user_quota_bytes: number; workspace_quota_bytes: number;
  site_asset_budget_bytes?: number | null; filesystem_reserve_bytes?: number; filesystem_reserve_percent?: number;
};
export type CapacityProfile = ProposedProfile & {
  schema_version: 2; site_asset_budget_bytes: number | null;
  filesystem_reserve_bytes: number; filesystem_reserve_percent: number;
};
export type CapacityForecast = {
  state: 'incomplete'; known_asset_lower_bound_bytes: number; unknown_preview_files: number; asset_observed_at: string;
  site_asset_budget: {proposed_bytes: number | null; maximum_possible_headroom_bytes: number | null};
  filesystem: {state: 'ready' | 'unknown'; observed_at: string; proposed_reserve_bytes: number | null;
    maximum_growth_above_reserve_bytes: number | null; reserve_shortfall_bytes: number | null};
  warnings: string[]; complete_for_enforcement: false; activation_supported: false;
};
export type Draft = {id: string; revision: number; profile: ProposedProfile; reason: string};
export type PolicyDrafts = {
  drafts: Draft[]; latest_revision: number; activation_supported: false;
  runtime_limits: {max_attachment_bytes: number; user_quota_bytes: number};
};
export type Observation = {id: string; observed_at: string; measurement: SiteUsage};
