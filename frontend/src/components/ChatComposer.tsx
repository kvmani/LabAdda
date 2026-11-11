import { useEffect, useRef, useState, type FormEvent } from "react";
import { accessDenied, api, errorMessage, newId, outcomeUnknown } from "../api";
import { useSession } from "../session";
import { UploadRecovery, useUploadQueue } from "./UploadRecovery";
import type { UploadedAsset } from "../uploads";
import type { ChatMessage, Workspace } from "../types";

type Intent = { body: string; client_id: string; parent_id: string | null; attachment_ids: string[] };
export function ChatComposer({
  ws,
  parentId = null,
  sent,
  denied,
}: {
  ws: Workspace;
  parentId?: string | null;
  sent: (message: ChatMessage) => void;
  denied: () => void;
}) {
  const [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState("");
  const [files, setFiles] = useState<UploadedAsset[]>([]);
  const { session } = useSession();
  const uploads = useUploadQueue(session?.limits.max_attachment_bytes ?? 20 * 1048576, (asset) =>
    setFiles((previous) => [...previous, asset]),
  );
  const maxFiles = session?.limits.max_attachments ?? 10;
  const attempt = useRef<Intent | null>(null),
    generation = useRef(0);
  useEffect(
    () => () => {
      ++generation.current;
    },
    [ws.id, parentId],
  );
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !ws.can_write || uploads.attempts.length || (!text.trim() && !files.length)) return;
    const token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      attempt.current ??= {
        body: text,
        client_id: newId("chat"),
        parent_id: parentId,
        attachment_ids: files.map((file) => file.id),
      };
      const message = await api<ChatMessage>(`/workspaces/${ws.id}/chat`, { body: attempt.current });
      if (token !== generation.current) return;
      attempt.current = null;
      setUnknown(false);
      setText("");
      setFiles([]);
      sent(message);
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        const uncertain = outcomeUnknown(e);
        setUnknown(uncertain);
        if (!uncertain) attempt.current = null;
        if (accessDenied(e)) denied();
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  if (!ws.can_write) return <p className="notice">Chat is read-only here.</p>;
  return (
    <form onSubmit={submit} aria-label={parentId ? "Reply to thread" : "Send chat message"}>
      <label>
        {parentId ? "Thread reply" : `Message ${ws.name}`}
        <input
          aria-label={parentId ? "Thread reply" : `Message ${ws.name}`}
          value={text}
          maxLength={4000}
          disabled={busy || unknown}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      <fieldset disabled={busy || unknown} className="chat-file-controls">
        <legend>Attachments</legend>
        <label>
          Attach files
          <input
            aria-label="Attach files"
            type="file"
            multiple
            accept="application/pdf,image/png,image/jpeg"
            onChange={(event) => {
              try {
                uploads.queue.add(Array.from(event.target.files ?? []), maxFiles - files.length);
              } catch (e: unknown) {
                setError(errorMessage(e));
              }
              event.target.value = "";
            }}
          />
        </label>
        <ul>
          {files.map((file) => (
            <li key={file.id}>
              {file.display_name}
              <button
                type="button"
                onClick={() => {
                  setFiles((current) => current.filter((row) => row.id !== file.id));
                  api(`/uploads/${file.id}`, { method: "DELETE" }).catch(() =>
                    setError("File removed from the message. Check storage if its upload still appears."),
                  );
                }}
              >
                Remove file: {file.display_name}
              </button>
            </li>
          ))}
        </ul>
      </fieldset>
      <UploadRecovery queue={uploads.queue} />
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {unknown && (
        <p role="status">
          Message outcome is unconfirmed. Retry the same message; its text and thread are kept unchanged.
        </p>
      )}
      <button type="submit" disabled={busy || uploads.attempts.length > 0}>
        {busy ? "Sending…" : unknown ? "Retry same message" : parentId ? "Send reply" : "Send"}
      </button>
    </form>
  );
}
