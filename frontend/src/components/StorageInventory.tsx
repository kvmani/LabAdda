import { fmtBytes } from "../format";
import "./storage.css";

export type InventorySummary = {
  checked_entries?: number;
  apparent_bytes?: number;
  allocated_bytes?: number;
  hardlink_aliases?: number;
  selected_pass_complete?: boolean;
  stop_reason?: string;
  issues_by_code?: Record<string, number>;
  classes?: Record<string, { entries: number; apparent_bytes: number }>;
};

const classes: Record<string, string> = {
  referenced_original: "Referenced originals",
  referenced_preview: "Referenced previews",
  temporary: "Temporary files",
  unreferenced_candidate: "Unreferenced candidates",
  unexpected: "Unexpected files",
};
const guidance: Record<string, string> = {
  reference_budget_exhausted:
    "Reference limit reached before scanning. Ask the host operator to review the scan budget.",
  scan_budget_exhausted: "Entry or time limit reached. This is only a partial observation.",
  inventory_unavailable:
    "Inventory unavailable. Ask the host operator to check database access and the asset directory.",
  unsupported_directory:
    "Unexpected or nested directories were skipped. Ask the host operator to inspect the storage layout.",
  changed_directory:
    "A directory changed during scanning. Repeat the observation after investigating concurrent changes.",
  different_filesystem: "A directory on another filesystem was skipped.",
  symlink_or_special_file:
    "Links or special files were skipped. Ask the host operator to inspect the storage layout.",
  entry_unavailable: "An entry could not be observed. Check permissions and concurrent changes.",
};
const bytes = (value: number | undefined) => (value === undefined ? "Not reported" : fmtBytes(value));

export function StorageInventory({ summary: s }: { summary: InventorySummary }) {
  return (
    <div className="storage-section">
      <p>
        <strong>Asset-directory inventory</strong> ·{" "}
        {s.selected_pass_complete ? "Directory pass finished" : "Incomplete observation"} ·{" "}
        {s.checked_entries ?? "Not reported"} entries checked
      </p>
      <p>
        Observed file lengths: {bytes(s.apparent_bytes)} · Reported file allocation:{" "}
        {bytes(s.allocated_bytes)} · Hard-link aliases: {s.hardlink_aliases ?? "Not reported"}
      </p>
      {s.classes && (
        <ul className="storage-steps">
          {Object.entries(s.classes).map(([key, value]) => (
            <li key={key}>
              {classes[key] ?? "Other files"}: {value.entries} entries · {bytes(value.apparent_bytes)}
            </li>
          ))}
        </ul>
      )}
      {s.stop_reason && (
        <p>{guidance[s.stop_reason] ?? "Ask the host operator to inspect this incomplete observation."}</p>
      )}
      {s.issues_by_code && (
        <ul className="storage-steps">
          {Object.entries(s.issues_by_code).map(([code, count]) => (
            <li key={code}>
              {count}: {guidance[code] ?? "Host operator investigation required."}
            </li>
          ))}
        </ul>
      )}
      <p className="storage-note">
        Observation only. Unreferenced candidates may belong to in-flight uploads and are not safe to delete.
        Live changes are possible. Allocation excludes directory metadata and may double-count shared extents.
        Class totals include hard-link aliases; overall file totals count each observed inode once. No
        integrity verification or deletion authority.
      </p>
    </div>
  );
}
