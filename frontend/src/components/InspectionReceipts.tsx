import type { InventorySummary } from "./StorageInventory";
import { fmtTime } from "../format";
import { StorageInventory } from "./StorageInventory";
import "./storage.css";

export type StorageReceipt = {
  id: string;
  status: string;
  finished_at: string | null;
  summary: InventorySummary & {
    checked_assets?: number;
    issue_count?: number;
    state?: string;
    verified_previews?: number;
    unknown_previews?: number;
    scope?: string;
    mode?: string;
    candidate_count?: number;
    applied_count?: number;
    stop_reason?: string;
    checked_items?: number;
    checked_boards?: number;
    correction_count?: number;
  };
};
const reconciliationStops: Record<string, string> = {
  plan_changed: "Plan changed; the host operator must run a new dry run.",
  byte_budget_exhausted: "Byte budget reached; reduce the batch size.",
  time_budget_exhausted: "Time budget reached; reduce the batch size.",
  reconciliation_busy: "Another reconciliation is running.",
  asset_root_unavailable: "Asset storage is unavailable; check host storage.",
  board_object_budget_exhausted: "Whiteboard object budget reached; reduce the batch size.",
};
const modeText = (mode?: string) =>
  mode === "dry_run" ? "Dry run" : mode === "apply" ? "Apply" : "Unknown mode";
const stopText = (code?: string) =>
  code ? ` · ${reconciliationStops[code] ?? "Host operator inspection required."}` : "";

function Detail({ summary: r }: { summary: StorageReceipt["summary"] }) {
  if (r.scope === "content_charge_reconciliation")
    return (
      <span className="storage-muted">
        {" "}
        · Text/whiteboard charge reconciliation {modeText(r.mode)}: {r.checked_items ?? "Not reported"} text
        items · {r.checked_boards ?? "Not reported"} boards · {r.correction_count ?? "Not reported"} ledger
        corrections planned · {r.applied_count ?? "Unconfirmed"} applied
        {stopText(r.stop_reason)}
      </span>
    );
  if (r.scope === "preview_metadata_reconciliation")
    return (
      <span className="storage-muted">
        {" "}
        · Preview reconciliation {modeText(r.mode)}: {r.candidate_count ?? "Not reported"} candidates ·{" "}
        {r.applied_count ?? "Unconfirmed"} metadata updates
        {stopText(r.stop_reason)}
      </span>
    );
  return (
    <span className="storage-muted">
      {" "}
      · Preview checks: {r.verified_previews ?? "Not reported"} verified ·{" "}
      {r.unknown_previews ?? "Not reported"} unknown expected measurements
    </span>
  );
}

/** Operator inspection, inventory and reconciliation receipts: metadata only. */
export function InspectionReceipts({ inspections }: { inspections: StorageReceipt[] }) {
  if (inspections.length === 0) return <p>No inspection receipts available.</p>;
  return (
    <ul className="storage-items">
      {inspections.map((r) => (
        <li key={r.id}>
          <p>
            {r.status}
            {["content_charge_reconciliation", "asset_directory_inventory"].includes(r.summary.scope ?? "")
              ? ""
              : ` · ${r.summary.checked_assets ?? "Not reported"} asset rows checked`}{" "}
            · {r.summary.issue_count ?? "Not reported"} issues ·{" "}
            {r.finished_at ? fmtTime(r.finished_at) : "No completion receipt"}
            {r.summary.scope !== "asset_directory_inventory" && <Detail summary={r.summary} />}
          </p>
          {r.summary.scope === "asset_directory_inventory" && <StorageInventory summary={r.summary} />}
        </li>
      ))}
    </ul>
  );
}
