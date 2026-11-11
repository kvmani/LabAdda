import type { ChargeBucket, LogicalCharges as Charges } from "../governance-types";
import { fmtBytes } from "../format";

const ROWS: [keyof Charges["by_type"], string][] = [
  ["post", "Posts and replies"],
  ["chat", "Chat messages"],
  ["board_object", "Whiteboard objects"],
  ["note", "Personal notes"],
];

function cell(bucket: ChargeBucket, state: "live" | "removed") {
  return `${fmtBytes(bucket[`${state}_bytes`])} · ${bucket[`${state}_items`]} ${bucket[`${state}_items`] === 1 ? "item" : "items"}`;
}

/** Versioned text/board logical charges (DL-07). Metadata only; never content. */
export function LogicalCharges({
  charges,
  scope,
}: {
  charges?: Charges;
  scope: "user" | "site" | "workspace";
}) {
  if (!charges)
    return <p className="muted">Text and whiteboard charges are not reported by this server version.</p>;
  const incomplete = charges.board_charges !== "complete";
  return (
    <>
      <h3>Text and whiteboard content (logical charges)</h3>
      <table>
        <caption className="sr-only">Logical charges by content type</caption>
        <thead>
          <tr>
            <th scope="col">Content</th>
            <th scope="col">Live</th>
            <th scope="col">Removed but stored</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.filter(
            ([key]) => charges.by_type[key] !== undefined && (scope !== "workspace" || key !== "note"),
          ).map(([key, label]) => (
            <tr key={key}>
              <th scope="row">
                {label}
                {scope === "site" && key === "note" ? " (site total only)" : ""}
              </th>
              <td>{cell(charges.by_type[key]!, "live")}</td>
              <td>{key === "post" ? cell(charges.by_type[key], "removed") : "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            <td>{fmtBytes(charges.live_logical_bytes)}</td>
            <td>{fmtBytes(charges.removed_logical_bytes)}</td>
          </tr>
        </tfoot>
      </table>
      {incomplete && (
        <p className="notice" role="status">
          Whiteboard totals are a lower bound:{" "}
          {scope !== "user" && charges.unreconciled_boards !== null ? (
            <>
              {charges.unreconciled_boards} board{charges.unreconciled_boards === 1 ? "" : "s"} with older
              history {charges.unreconciled_boards === 1 ? "has" : "have"} not been reconciled yet. A host
              operator can run <code>labadda reconcile-charges</code>.
            </>
          ) : (
            "some boards with older history have not been reconciled yet."
          )}
        </p>
      )}
      <p className="muted small">
        Measured as UTF-8 bytes of {scope === "user" ? "the text you wrote" : "user-written text"} (
        {charges.methods.text}) and of each live whiteboard object ({charges.methods.board}). These are
        logical charges, not disk usage. Attachments are counted separately; whiteboard history and database
        overhead are site storage, shown to operators and not charged to anyone. They do not change any limit.
      </p>
    </>
  );
}
