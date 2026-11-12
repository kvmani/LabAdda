import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, asApiError, errorMessage } from "../../api";
import { fmtTime, isoToLocal, localToIso } from "../../format";
import { Banner, Button, Card, DateInput, Select, TextArea } from "../../ui";
import type { Notice } from "./settingsTypes";

type Props = { current: Notice | null; maxLength: number; onSaved: (notice: Notice | null) => void };

/** Publish, replace or remove the one site notice (AD-11). */
export function NoticeEditor({ current, maxLength, onSaved }: Props) {
  const [message, setMessage] = useState(current?.message ?? "");
  const [level, setLevel] = useState<string>(current?.level ?? "info");
  const [starts, setStarts] = useState(current ? isoToLocal(current.starts_at) : "");
  const [ends, setEnds] = useState(current ? isoToLocal(current.ends_at) : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  async function save(remove: boolean) {
    setBusy(true);
    setError("");
    setDone("");
    try {
      const result = await api<{ banner: Notice | null }>("/admin/settings/banner", {
        method: "PUT",
        body: remove
          ? { message: "", expected_revision: current?.revision ?? 0 }
          : {
              message,
              level,
              starts_at: localToIso(starts),
              ends_at: localToIso(ends),
              expected_revision: current?.revision ?? 0,
            },
      });
      onSaved(result.banner);
      if (remove) setMessage("");
      setDone(remove ? "The site notice was removed." : "The site notice was published.");
    } catch (failure) {
      const known = asApiError(failure);
      setError(
        known?.code === "banner_changed"
          ? "Someone else changed the notice. Reload this page to see their version."
          : errorMessage(failure),
      );
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void save(false);
  }

  return (
    <Card title="Site notice">
      <p className="admin-note">
        One short message shown at the top of every page for everyone who is signed in. It disappears by
        itself at the end time. <Link to="/help/admin/site-notice">How to publish a notice</Link>
      </p>
      {current && (
        <p>
          Currently set, from {fmtTime(current.starts_at)} to {fmtTime(current.ends_at)}.
        </p>
      )}
      <form className="admin-form" onSubmit={submit}>
        <TextArea
          label="Notice text"
          hint={`Plain text, up to ${maxLength} characters.`}
          value={message}
          maxLength={maxLength}
          rows={3}
          required
          onChange={(event) => setMessage(event.target.value)}
        />
        <Select
          label="Notice level"
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
            required
            value={ends}
            onChange={(event) => setEnds(event.target.value)}
          />
        </div>
        {error && (
          <p role="alert" className="ui-field__error">
            {error}
          </p>
        )}
        {done && <p role="status">{done}</p>}
        {message.trim() && (
          <div aria-label="Preview of the notice">
            <Banner level={level === "warning" ? "warning" : "info"}>{message}</Banner>
          </div>
        )}
        <div className="admin-form__row">
          <Button type="submit" variant="primary" busy={busy} busyLabel="Saving…">
            Publish notice
          </Button>
          {current && (
            <Button variant="danger" disabled={busy} onClick={() => void save(true)}>
              Remove notice
            </Button>
          )}
        </div>
      </form>
    </Card>
  );
}
