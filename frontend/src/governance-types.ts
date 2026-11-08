export type OriginalMeasurement = {
  state: 'partial'; source: 'asset_metadata'; observed_at: string; tracked_files: number;
  pending_upload_original_bytes: number; tracked_original_bytes: number; provisional_original_bytes: number; committed_original_bytes: number;
  unmeasured: string[]; complete_for_enforcement: false;
};
export type UserUsage = {
  measurement: OriginalMeasurement;
  runtime_limit: {bytes: number; source: string; policy_proposals_enforced: false};
};
export type SiteUsage = {
  assets: OriginalMeasurement;
  filesystem: {state: string; free_bytes: number | null; total_bytes: number | null; free_inodes: number | null};
};
export type ProposedProfile = {
  schema_version: number; mode: 'observation'; max_attachment_bytes: number;
  user_quota_bytes: number; workspace_quota_bytes: number;
};
export type Draft = {id: string; revision: number; profile: ProposedProfile; reason: string};
export type PolicyDrafts = {
  drafts: Draft[]; latest_revision: number; activation_supported: false;
  runtime_limits: {max_attachment_bytes: number; user_quota_bytes: number};
};
export type Observation = {id: string; observed_at: string; measurement: SiteUsage};
