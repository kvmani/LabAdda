import { useRef, useState, type FormEvent } from "react";
import { api, newId, errorMessage } from "../api";
import { localToIso } from "../format";
import { useSession } from "../session";
import type { Attachment, Workspace } from "../types";
import { Button, Card, Checkbox, DateInput, Field, IconButton, Tag, TextArea } from "../ui";
import { UploadRecovery, useUploadQueue } from "./UploadRecovery";
import "./post-composer.css";

const drafts = new Map<string, string>(); // drafts stay scoped to their original workspace

export function PostComposer({ ws, onPosted }: { ws: Workspace; onPosted: () => void }) {
  const { session } = useSession();
  const [body, setBodyState] = useState(drafts.get(ws.id) ?? "");
  const [official, setOfficial] = useState(false);
  const [due, setDue] = useState("");
  const [remind, setRemind] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const clientId = useRef(newId("p"));
  const limits = session!.limits;
  const uploads = useUploadQueue(limits.max_attachment_bytes, (asset) => {
    setFiles((prev) => (prev.some((f) => f.id === asset.id) ? prev : [...prev, asset]));
  });

  const setBody = (v: string) => {
    setBodyState(v);
    drafts.set(ws.id, v);
    setSaved(false);
  };

  function addFiles(list: FileList | null) {
    if (!list) return;
    setError(null);
    try {
      uploads.queue.add(Array.from(list), limits.max_attachments - files.length);
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (uploads.attempts.length) return setError("Resolve or dismiss pending uploads before posting.");
    setBusy(true);
    setError(null);
    try {
      await api(`/workspaces/${ws.id}/posts`, {
        body: {
          body,
          kind: official ? "official" : "discussion",
          due_at: localToIso(due),
          remind_at: localToIso(remind),
          attachment_ids: files.map((f) => f.id),
          client_id: clientId.current,
        },
      });
      // Clear only after the server confirms the commit.
      setBody("");
      drafts.delete(ws.id);
      setFiles([]);
      setDue("");
      setRemind("");
      setOfficial(false);
      clientId.current = newId("p");
      setSaved(true);
      onPosted();
    } catch (e: unknown) {
      setError(errorMessage(e) + " Your text is kept so you can try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!ws.can_write) {
    return (
      <Card>
        <p className="composer__audience">
          {ws.archived
            ? "This workspace is archived. Content stays readable but no one can post."
            : "Posting is limited to stewards in this workspace."}
        </p>
      </Card>
    );
  }
  return (
    <Card>
      <form className="composer" onSubmit={submit} aria-label={`Post to ${ws.name}`}>
        <div className="composer__intro">
          <strong>Post to {ws.name}</strong>
          <span className="composer__audience">
            Audience:{" "}
            {ws.kind === "group"
              ? "group members only"
              : ws.kind === "project"
                ? "project members only"
                : `members of ${ws.name} and its sub-units`}
          </span>
        </div>
        <TextArea
          label="Message"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Share an update, @mention a colleague…"
          rows={3}
          required
          maxLength={10000}
        />
        <div className="composer__options">
          <DateInput kind="datetime-local" label="Due" value={due} onChange={(e) => setDue(e.target.value)} />
          <DateInput
            kind="datetime-local"
            label="Remind"
            value={remind}
            onChange={(e) => setRemind(e.target.value)}
          />
          <Field label="Attach">
            {(control) => (
              <input
                {...control}
                type="file"
                accept="application/pdf,image/png,image/jpeg"
                multiple
                disabled={busy}
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
            )}
          </Field>
          {ws.can_moderate && (
            <Checkbox
              label="Official notice"
              checked={official}
              onChange={(e) => setOfficial(e.target.checked)}
            />
          )}
        </div>
        {files.length > 0 && (
          <ul className="composer__files">
            {files.map((f) => (
              <li key={f.id}>
                <Tag>{f.display_name}</Tag>
                <IconButton
                  icon="close"
                  size="sm"
                  label={`Remove ${f.display_name}`}
                  onClick={() => {
                    api(`/uploads/${f.id}`, { method: "DELETE" }).catch(() => undefined);
                    setFiles(files.filter((x) => x.id !== f.id));
                  }}
                />
              </li>
            ))}
          </ul>
        )}
        <UploadRecovery queue={uploads.queue} />
        {error && (
          <p className="composer__error" role="alert">
            {error}
          </p>
        )}
        <div className="composer__submit">
          <Button
            variant="primary"
            type="submit"
            busy={busy}
            busyLabel="Posting…"
            disabled={uploads.attempts.length > 0}
          >
            Post
          </Button>
          {saved && (
            <span className="composer__saved" role="status">
              Posted
            </span>
          )}
        </div>
      </form>
    </Card>
  );
}
