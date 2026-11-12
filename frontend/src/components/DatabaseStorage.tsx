import type { DatabaseStorage as Storage } from "../governance-types";
import { fmtBytes } from "../format";
import "./storage.css";

const LABELS: [keyof Storage["categories"], string][] = [
  ["collaboration_text", "Posts, chat and notifications"],
  ["board_history", "Whiteboard history and snapshots"],
  ["personal_notes", "Personal notes (site total)"],
  ["file_metadata", "File records and upload receipts"],
  ["identity_and_access", "Accounts, sessions and workspaces"],
  ["audit_and_governance", "Audit, governance and charge ledger"],
];

/** Physical PostgreSQL storage (DL-07): site overhead, measured separately from logical charges. */
export function DatabaseStorage({ storage }: { storage?: Storage }) {
  if (!storage) return null;
  if (storage.state !== "ready")
    return <p className="storage-note">Database storage is currently unknown. Retry later.</p>;
  return (
    <section className="storage-section">
      <h3 className="storage-subheading">Database storage (physical)</h3>
      <div className="storage-table-scroll" role="region" aria-label="Database storage" tabIndex={0}>
        <table className="storage-table">
          <caption className="ui-visually-hidden">Physical database storage by category</caption>
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col">Size including indexes</th>
            </tr>
          </thead>
          <tbody>
            {LABELS.map(([key, label]) => (
              <tr key={key}>
                <th scope="row">{label}</th>
                <td>{fmtBytes(storage.categories[key])}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">System catalogs and free space</th>
              <td>{fmtBytes(storage.other_bytes)}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Database total</th>
              <td>{fmtBytes(storage.database_bytes)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="storage-muted">
        Whiteboard history currently holds{" "}
        {storage.board_history.retained_operations ?? "an unknown number of"} retained operations and{" "}
        {storage.board_history.snapshots ?? "an unknown number of"} snapshots. Physical storage is shared site
        overhead: it is not charged to any user or workspace and does not change any limit.
      </p>
    </section>
  );
}
