import { Drawer } from "../../ui";
import { fmtTime } from "../../format";
import { fieldLabel, outcomeLabel, showValue } from "./model";
import type { AuditEvent } from "./types";

const HANDLED = new Set(["before", "after"]);

function Recorded({ detail }: { detail: Record<string, unknown> }) {
  const rows = Object.entries(detail).filter(
    ([key]) => !HANDLED.has(key) && !key.endsWith("_before") && !key.endsWith("_after"),
  );
  if (!rows.length) return <p>No further details were recorded.</p>;
  return (
    <dl className="audit-record">
      {rows.map(([key, value]) => (
        <div key={key}>
          <dt>{fieldLabel(key)}</dt>
          <dd>{showValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The sentence first, then what changed, then every recorded value; records are read-only. */
export function AuditDetail({
  event,
  timezone,
  onClose,
}: {
  event: AuditEvent;
  timezone: string;
  onClose: () => void;
}) {
  return (
    <Drawer open title="Audit entry" onClose={onClose}>
      <p className="audit-sentence">{event.sentence}</p>
      <dl className="audit-record">
        <div>
          <dt>When</dt>
          <dd>{fmtTime(event.created_at, timezone)}</dd>
        </div>
        <div>
          <dt>Kind of change</dt>
          <dd>{event.group_label}</dd>
        </div>
        <div>
          <dt>Outcome</dt>
          <dd>{outcomeLabel(event.outcome)}</dd>
        </div>
        <div>
          <dt>Stated reason</dt>
          <dd>{event.reason || "No reason was given."}</dd>
        </div>
      </dl>
      <h3>Before and after</h3>
      {event.changes.length ? (
        <table className="audit-changes">
          <caption className="audit-visually-hidden">Values before and after the change</caption>
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col">Before</th>
              <th scope="col">After</th>
            </tr>
          </thead>
          <tbody>
            {event.changes.map((change) => (
              <tr key={change.field}>
                <th scope="row">{fieldLabel(change.field)}</th>
                <td>{showValue(change.before)}</td>
                <td>{showValue(change.after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No before and after values were recorded.</p>
      )}
      <h3>Recorded details</h3>
      <Recorded detail={event.detail} />
    </Drawer>
  );
}
