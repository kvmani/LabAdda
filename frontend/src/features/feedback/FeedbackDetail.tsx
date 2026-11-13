import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api";
import { fmtBytes, fmtTime } from "../../format";
import { Button, Drawer, ErrorState, Select, Skeleton, TextArea } from "../../ui";
import { STATUS_OPTIONS, categoryWord, mailSentence } from "./model";
import type { FeedbackDetail, FeedbackStatus } from "./types";
import "./feedback.css";

type Props = {
  id: string;
  timezone: string;
  emailConfigured: boolean;
  onClose: () => void;
  onChanged: () => void;
};

/** Opening a message is recorded in the audit trail; the sender knew administrators would read it. */
export function FeedbackDetailDrawer({ id, timezone, emailConfigured, onClose, onChanged }: Props) {
  const [item, setItem] = useState<FeedbackDetail | null>(null);
  const [loadError, setLoadError] = useState("");
  const [status, setStatus] = useState<FeedbackStatus>("new");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const show = (detail: FeedbackDetail) => {
    setItem(detail);
    setStatus(detail.status);
    setNote(detail.admin_note ?? "");
  };
  useEffect(() => {
    let current = true;
    api<FeedbackDetail>(`/admin/feedback/${id}`)
      .then((detail) => current && show(detail))
      .catch((failure: unknown) => current && setLoadError(errorMessage(failure)));
    return () => {
      current = false;
    };
  }, [id]);

  async function save() {
    if (!item) return;
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      show(
        await api<FeedbackDetail>(`/admin/feedback/${id}`, {
          method: "PATCH",
          body: { expected_revision: item.revision, status, admin_note: note },
        }),
      );
      setSaved(true);
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }
  async function resend() {
    setSaving(true);
    setError("");
    try {
      show(await api<FeedbackDetail>(`/admin/feedback/${id}/resend`, { method: "POST", body: {} }));
      onChanged();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer open title="Feedback" onClose={onClose}>
      {loadError ? (
        <ErrorState message={loadError} />
      ) : !item ? (
        <Skeleton />
      ) : (
        <>
          <p>
            <strong>{categoryWord(item.category)}</strong> from {item.username},{" "}
            {fmtTime(item.created_at, timezone)}
          </p>
          <p className="feedback-message">{item.message}</p>
          <dl className="feedback-facts">
            <dt>Page</dt>
            <dd>{item.route ?? "Not given"}</dd>
            <dt>Software version</dt>
            <dd>{item.software_version}</dd>
            <dt>Commit</dt>
            <dd>{item.commit}</dd>
            <dt>Browser</dt>
            <dd>{item.user_agent ?? "Not given"}</dd>
            <dt>Screen size</dt>
            <dd>{item.screen ?? "Not given"}</dd>
            <dt>E-mail copy</dt>
            <dd>{mailSentence(item.email, emailConfigured)}</dd>
          </dl>
          {item.email.status === "failed" && (
            <p>
              <Button onClick={() => void resend()} disabled={saving}>
                Send e-mail again
              </Button>
            </p>
          )}
          <h3>Files</h3>
          {item.attachments.length === 0 ? (
            <p>No files were attached.</p>
          ) : (
            <>
              <div className="feedback-previews">
                {item.attachments
                  .filter((file) => file.preview_url)
                  .map((file) => (
                    <img key={file.id} src={file.preview_url ?? ""} alt={`Screenshot ${file.display_name}`} />
                  ))}
              </div>
              <ul className="feedback-files" aria-label="Attached files">
                {item.attachments.map((file) => (
                  <li key={file.id}>
                    <a href={file.url} target="_blank" rel="noreferrer">
                      Open {file.display_name}
                    </a>
                    <span>{fmtBytes(file.size)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <form
            className="feedback-form"
            onSubmit={(submitted) => {
              submitted.preventDefault();
              void save();
            }}
          >
            <Select
              label="Status"
              options={STATUS_OPTIONS}
              value={status}
              onChange={(changed) => setStatus(changed.target.value as FeedbackStatus)}
            />
            <TextArea
              label="Administrator note"
              hint="Only administrators see this note."
              value={note}
              maxLength={2000}
              onChange={(changed) => setNote(changed.target.value)}
            />
            {error && <p role="alert">{error}</p>}
            {saved && <p role="status">Saved.</p>}
            <div className="feedback-actions">
              <Button type="submit" variant="primary" disabled={saving}>
                {saving ? "Saving…" : "Save status and note"}
              </Button>
            </div>
          </form>
        </>
      )}
    </Drawer>
  );
}
