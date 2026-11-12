import { DataTable, type Column } from "../ui";
import { fmtBytes as bytes } from "../format";
import type { Draft } from "../governance-types";

const columns: Column<Draft>[] = [
  { key: "revision", header: "Revision", render: (d) => d.revision },
  {
    key: "limits",
    header: "Proposed file / user / workspace limits",
    render: (d) =>
      `${bytes(d.profile.max_attachment_bytes)} / ${bytes(d.profile.user_quota_bytes)} / ${bytes(d.profile.workspace_quota_bytes)}`,
  },
  {
    key: "site",
    header: "Proposed site assets / reserve",
    render: (d) =>
      d.profile.schema_version === 2
        ? `${d.profile.site_asset_budget_bytes === null ? "Not configured" : bytes(d.profile.site_asset_budget_bytes ?? null)} / ${bytes(d.profile.filesystem_reserve_bytes ?? null)} or ${d.profile.filesystem_reserve_percent}% (greater)`
        : "Not recorded in version 1",
  },
  { key: "reason", header: "Reason", render: (d) => d.reason },
  { key: "status", header: "Status", render: () => "Draft only" },
];

/** Saved proposals are immutable drafts; none is enforced. */
export function ProposalHistory({ drafts }: { drafts: Draft[] }) {
  return (
    <DataTable caption="Recent immutable proposals" columns={columns} rows={drafts} rowKey={(d) => d.id} />
  );
}
