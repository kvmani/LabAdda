import { useEffect, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { accessDenied, api, errorMessage, newId, outcomeUnknown } from "../api";
import { useSession } from "../session";
import { UploadRecovery, useUploadQueue } from "./UploadRecovery";
import type { UploadedAsset } from "../uploads";
import type { ChatMessage, Workspace } from "../types";
import { Button, Field, TextInput } from "../ui";
import "./chat.css";

type Intent = { body: string; client_id: string; parent_id: string | null; attachment_ids: string[] };
type ComposerProps = {
  ws: Workspace;
  parentId?: string | null;
  sent: (message: ChatMessage) => void;
  denied: () => void;
};

/** Sends one message; a retry after an unknown outcome reuses the same intent and client id. */
function useChatSend(
  { ws, parentId = null, sent, denied }: ComposerProps,
  files: UploadedAsset[],
  clearFiles: () => void,
) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [error, setError] = useState("");
  const attempt = useRef<Intent | null>(null);
  const generation = useRef(0);

  useEffect(
    () => () => {
      generation.current += 1;
    },
    [ws.id, parentId],
  );

  function resetAfterSend() {
    attempt.current = null;
    setUnknown(false);
    setText("");
    clearFiles();
  }

  async function submit(event: FormEvent, uploadsPending: boolean) {
    event.preventDefault();
    if (busy || !ws.can_write || uploadsPending || (!text.trim() && !files.length)) return;
    generation.current += 1;
    const token = generation.current;
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
      resetAfterSend();
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

  return { text, setText, busy, unknown, error, setError, submit };
}

function AttachmentPicker({
  files,
  setFiles,
  uploads,
  setError,
  disabled,
}: {
  files: UploadedAsset[];
  setFiles: Dispatch<SetStateAction<UploadedAsset[]>>;
  uploads: ReturnType<typeof useUploadQueue>;
  setError: (message: string) => void;
  disabled: boolean;
}) {
  const { session } = useSession();
  const maxFiles = session?.limits.max_attachments ?? 10;

  function removeFile(file: UploadedAsset) {
    setFiles((current) => current.filter((row) => row.id !== file.id));
    api(`/uploads/${file.id}`, { method: "DELETE" }).catch(() =>
      setError("File removed from the message. Check storage if its upload still appears."),
    );
  }

  return (
    <fieldset disabled={disabled} className="chat-composer__files">
      <legend>Attachments</legend>
      <Field label="Attach files">
        {(control) => (
          <input
            {...control}
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
        )}
      </Field>
      <ul>
        {files.map((file) => (
          <li key={file.id}>
            <span>{file.display_name}</span>
            <Button variant="quiet" size="sm" onClick={() => removeFile(file)}>
              Remove file: {file.display_name}
            </Button>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

export function ChatComposer(props: ComposerProps) {
  const { ws, parentId = null } = props;
  const [files, setFiles] = useState<UploadedAsset[]>([]);
  const { session } = useSession();
  const uploads = useUploadQueue(session?.limits.max_attachment_bytes ?? 20 * 1048576, (asset) =>
    setFiles((previous) => [...previous, asset]),
  );
  const send = useChatSend(props, files, () => setFiles([]));
  const { busy, unknown } = send;
  if (!ws.can_write) return <p className="chat__meta">Chat is read-only here.</p>;

  return (
    <form
      className="chat-composer"
      onSubmit={(event) => send.submit(event, uploads.attempts.length > 0)}
      aria-label={parentId ? "Reply to thread" : "Send chat message"}
    >
      <TextInput
        label={parentId ? "Thread reply" : `Message ${ws.name}`}
        value={send.text}
        maxLength={4000}
        disabled={busy || unknown}
        onChange={(e) => send.setText(e.target.value)}
      />
      <AttachmentPicker
        files={files}
        setFiles={setFiles}
        uploads={uploads}
        setError={send.setError}
        disabled={busy || unknown}
      />
      <UploadRecovery queue={uploads.queue} />
      {send.error && (
        <p className="chat__error" role="alert">
          {send.error}
        </p>
      )}
      {unknown && (
        <p role="status">
          Message outcome is unconfirmed. Retry the same message; its text and thread are kept unchanged.
        </p>
      )}
      <div>
        <Button
          variant="primary"
          type="submit"
          disabled={uploads.attempts.length > 0}
          busy={busy}
          busyLabel="Sending…"
        >
          {unknown ? "Retry same message" : parentId ? "Send reply" : "Send"}
        </Button>
      </div>
    </form>
  );
}
