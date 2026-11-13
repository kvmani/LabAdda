import { useState, type FormEvent } from "react";
import { api, asApiError, errorMessage } from "../../api";
import { isoToLocal, localToIso } from "../../format";
import { Button, Checkbox, DateInput, Dialog, Select, TextArea } from "../../ui";
import type { Broadcast } from "./types";

type Props = {
  /** The broadcast being edited, or null to add a new one. */
  current: Broadcast | null;
  maxLength: number;
  onClose: () => void;
  onSaved: () => void;
};

/** Add or edit one broadcast. The draft stays in the dialog when the save fails. */
export function BroadcastDialog({ current, maxLength, onClose, onSaved }: Props) {
  const [message, setMessage] = useState(current?.message ?? "");
  const [level, setLevel] = useState<string>(current?.level ?? "info");
  const [starts, setStarts] = useState(isoToLocal(current?.starts_at ?? null));
  const [ends, setEnds] = useState(isoToLocal(current?.ends_at ?? null));
  const [active, setActive] = useState(current?.active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const fields = { message, level, starts_at: localToIso(starts), ends_at: localToIso(ends), active };
    try {
      if (current) {
        await api(`/admin/broadcasts/${current.id}`, {
          method: "PATCH",
          body: { ...fields, expected_revision: current.revision },
        });
      } else {
        await api("/admin/broadcasts", { method: "POST", body: fields });
      }
      onSaved();
    } catch (failure) {
      setError(
        asApiError(failure)?.code === "broadcast_changed"
          ? "Someone else changed this message. Close this window, reload the page and try again."
          : errorMessage(failure),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open
      title={current ? "Edit broadcast message" : "Add broadcast message"}
      onClose={busy ? () => undefined : onClose}
    >
      <form className="admin-form" onSubmit={(event) => void save(event)}>
        <TextArea
          label="Message"
          hint={`Plain text, up to ${maxLength} characters. Do not put anything private here: everyone signed in sees it.`}
          value={message}
          maxLength={maxLength}
          rows={3}
          required
          onChange={(event) => setMessage(event.target.value)}
        />
        <Select
          label="Level"
          value={level}
          options={[
            { value: "info", label: "Information" },
            { value: "warning", label: "Warning" },
          ]}
          onChange={(event) => setLevel(event.target.value)}
        />
        <div className="admin-form__row">
          <DateInput
            label="Show from"
            kind="datetime-local"
            hint="Leave empty to start now. Times are in this computer's time zone."
            value={starts}
            onChange={(event) => setStarts(event.target.value)}
          />
          <DateInput
            label="Show until"
            kind="datetime-local"
            hint="Leave empty to keep showing it until you turn it off or delete it."
            value={ends}
            onChange={(event) => setEnds(event.target.value)}
          />
        </div>
        <Checkbox label="Show this message" checked={active} onChange={(e) => setActive(e.target.checked)} />
        {error && (
          <p role="alert" className="ui-field__error">
            {error}
          </p>
        )}
        <div className="admin-form__row">
          <Button type="submit" variant="primary" busy={busy} busyLabel="Saving…">
            {current ? "Save message" : "Add message"}
          </Button>
          <Button variant="quiet" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
