import { useState } from "react";
import { Link } from "react-router-dom";
import { api, asApiError, errorMessage } from "../../api";
import { fmtTime } from "../../format";
import { Button, Drawer, StatusPill, TextArea } from "../../ui";
import { severityPill, stateLabel } from "./model";
import type { OpsEvent } from "./types";

type Props = {
  event: OpsEvent;
  timezone: string;
  readOnly: boolean;
  onClose: () => void;
  onChanged: (event: OpsEvent) => void;
};

function Facts({ event, timezone }: { event: OpsEvent; timezone: string }) {
  const when = (iso: string | null) => (iso ? fmtTime(iso, timezone) : "");
  return (
    <dl className="events-facts">
      <dt>Where</dt>
      <dd>{event.component_label}</dd>
      <dt>Status</dt>
      <dd>{stateLabel(event.state)}</dd>
      <dt>First seen</dt>
      <dd>{when(event.first_at)}</dd>
      <dt>Last seen</dt>
      <dd>{when(event.last_at)}</dd>
      <dt>Times seen</dt>
      <dd>{event.count}</dd>
      {event.acknowledged_at && (
        <>
          <dt>Acknowledged by</dt>
          <dd>
            {event.acknowledged_by?.display_name ?? "Unknown"}, {when(event.acknowledged_at)}
          </dd>
          <dt>Their note</dt>
          <dd>{event.note}</dd>
        </>
      )}
      {event.resolved_at && (
        <>
          <dt>Resolved</dt>
          <dd>{when(event.resolved_at)}</dd>
        </>
      )}
    </dl>
  );
}

/** Acknowledging records who has seen a problem; it never changes the system or hides the failure. */
export function EventDetail({ event, timezone, readOnly, onClose, onChanged }: Props) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const pill = severityPill[event.severity];
  async function submit(action: "acknowledge" | "resolve") {
    if (action === "acknowledge" && !note.trim()) {
      setError("Write a short note saying what you know or will do.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const changed = await api<OpsEvent>(`/admin/events/${event.id}/${action}`, { body: { note } });
      setNote("");
      onChanged(changed);
    } catch (failure) {
      setError(asApiError(failure)?.message ?? errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }
  return (
    <Drawer open title="System event" onClose={onClose}>
      <p className="events-summary">{event.summary}</p>
      <p>
        <StatusPill {...pill} />
      </p>
      <Facts event={event} timezone={timezone} />
      {event.help && (
        <p>
          <Link to={`/help/${event.help}`}>Open the guide for this problem</Link>
        </p>
      )}
      {event.state !== "resolved" &&
        (readOnly ? (
          <p>Only administrators can acknowledge or resolve events.</p>
        ) : (
          <form
            className="events-form"
            onSubmit={(submitted) => {
              submitted.preventDefault();
              void submit("acknowledge");
            }}
          >
            <TextArea
              label="Note"
              hint="Say what you know or what you will do. Everyone who opens this event can read it."
              value={note}
              maxLength={500}
              onChange={(changed) => setNote(changed.target.value)}
            />
            {error && <p role="alert">{error}</p>}
            <div className="events-form__actions">
              {event.state === "open" && (
                <Button type="submit" variant="primary" disabled={saving}>
                  Acknowledge
                </Button>
              )}
              <Button disabled={saving} onClick={() => void submit("resolve")}>
                Mark as resolved
              </Button>
            </div>
          </form>
        ))}
    </Drawer>
  );
}
