import { useEffect, useRef, useState, type FormEvent } from "react";
import { accessDenied, api, errorMessage, newId, outcomeUnknown } from "../api";
import { useSession } from "../session";
import { UploadRecovery, useUploadQueue } from "./UploadRecovery";
import type { UploadedAsset } from "../uploads";
import type { ChatMessage, Workspace } from "../types";
import { Button } from "../ui";
import "./chat.css";

type Intent = { body: string; client_id: string; parent_id: string | null; attachment_ids: string[] };

export type ComposerProps = {
  ws: Workspace;
  parentId?: string | null;
  replyingTo?: ChatMessage | null;
  onClearReply?: () => void;
  sent: (message: ChatMessage) => void;
  denied: () => void;
};

const QUICK_EMOJIS = ["👍", "❤️", "😊", "😂", "🎉", "🚀", "👏", "🙏", "🔥", "💡"];

function useChatSend(props: ComposerProps, files: UploadedAsset[], clearFiles: () => void) {
  const { ws, parentId = null, replyingTo = null, onClearReply, sent, denied } = props;
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
    onClearReply?.();
  }

  async function submit(event: FormEvent, uploadsPending: boolean) {
    event.preventDefault();
    if (busy || !ws.can_contribute || uploadsPending || (!text.trim() && !files.length)) return;
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    try {
      const author = replyingTo?.author?.display_name ?? "User";
      const snippet = ((replyingTo?.body ?? "").split("\n")[0] ?? "").slice(0, 100);
      const formattedBody = replyingTo ? `> [${author}]: ${snippet}\n\n${text}` : text;

      attempt.current ??= {
        body: formattedBody,
        client_id: newId("chat"),
        parent_id: parentId ?? replyingTo?.parent_id ?? replyingTo?.id ?? null,
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

export function ChatComposer(props: ComposerProps) {
  const { ws, parentId = null, replyingTo = null, onClearReply } = props;
  const [files, setFiles] = useState<UploadedAsset[]>([]);
  const [showEmoji, setShowEmoji] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { session } = useSession();
  const maxFiles = session?.limits.max_attachments ?? 10;
  const uploads = useUploadQueue(session?.limits.max_attachment_bytes ?? 20 * 1048576, (asset) =>
    setFiles((previous) => [...previous, asset]),
  );
  const send = useChatSend(props, files, () => setFiles([]));
  const { busy, unknown } = send;

  if (!ws.can_contribute)
    return (
      <p className="chat__meta" style={{ padding: "12px 16px" }}>
        You can view chat. Contributions are limited to unit representatives or stewards.
      </p>
    );

  function removeFile(file: UploadedAsset) {
    setFiles((current) => current.filter((row) => row.id !== file.id));
    api(`/uploads/${file.id}`, { method: "DELETE" }).catch(() =>
      send.setError("File removed from the message. Check storage if its upload still appears."),
    );
  }

  function insertEmoji(emoji: string) {
    send.setText((prev) => prev + emoji);
  }

  const hasContent = send.text.trim().length > 0 || files.length > 0;

  return (
    <form
      className="chat-composer"
      onSubmit={(event) => send.submit(event, uploads.attempts.length > 0)}
      aria-label={parentId ? "Reply to thread" : "Send chat message"}
    >
      {/* Quoted reply preview */}
      {replyingTo && (
        <div className="chat-composer__quote-preview">
          <div className="chat-composer__quote-preview-body">
            <span className="chat-composer__quote-preview-author">
              {replyingTo.author?.display_name ?? "User"}
            </span>
            <span className="chat-composer__quote-preview-text">{replyingTo.body}</span>
          </div>
          <button
            type="button"
            className="chat-composer__quote-dismiss"
            onClick={onClearReply}
            aria-label="Cancel reply"
            disabled={busy || unknown}
          >
            ✕
          </button>
        </div>
      )}

      {/* Files list */}
      {files.length > 0 && (
        <div className="chat-composer__files">
          {files.map((file) => (
            <span key={file.id} className="chat-composer__file-tag">
              📄 {file.display_name}
              <Button
                variant="quiet"
                size="sm"
                aria-label={`Remove file ${file.display_name}`}
                disabled={busy || unknown}
                onClick={() => removeFile(file)}
              >
                ✕
              </Button>
            </span>
          ))}
        </div>
      )}

      {/* Emoji bar */}
      {showEmoji && (
        <div className="chat-composer__emoji-bar">
          {QUICK_EMOJIS.map((emoji) => (
            <button
              key={emoji}
              type="button"
              className="chat-composer__emoji-item"
              disabled={busy || unknown}
              onClick={() => insertEmoji(emoji)}
            >
              {emoji}
            </button>
          ))}
        </div>
      )}

      {/* Main Composer Bar */}
      <div className="chat-composer__bar">
        {/* Attachment + button */}
        <button
          type="button"
          className="chat-composer__btn"
          title="Attach files"
          aria-label="Attach files"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy || unknown}
        >
          ➕
        </button>
        <input
          ref={fileInputRef}
          type="file"
          disabled={busy || unknown}
          multiple
          hidden
          accept="application/pdf,image/png,image/jpeg"
          onChange={(event) => {
            try {
              uploads.queue.add(Array.from(event.target.files ?? []), maxFiles - files.length);
            } catch (e: unknown) {
              send.setError(errorMessage(e));
            }
            event.target.value = "";
          }}
        />

        {/* Emoji toggle button */}
        <button
          type="button"
          className="chat-composer__btn"
          title="Insert emoji"
          aria-label="Insert emoji"
          disabled={busy || unknown}
          onClick={() => setShowEmoji((v) => !v)}
        >
          😊
        </button>

        {/* Rounded Input Pill */}
        <div className="chat-composer__input-wrapper">
          <input
            className="chat-composer__input"
            placeholder={parentId ? "Reply to thread…" : "Type a message"}
            value={send.text}
            maxLength={4000}
            disabled={busy || unknown}
            onChange={(e) => send.setText(e.target.value)}
            aria-label={parentId ? "Thread reply" : `Message ${ws.name}`}
          />
        </div>

        <button
          type="submit"
          className="chat-composer__send-btn"
          title={unknown ? "Retry same message" : parentId ? "Send reply" : "Send"}
          aria-label={unknown ? "Retry same message" : parentId ? "Send reply" : "Send"}
          disabled={!hasContent || uploads.attempts.length > 0 || busy}
        >
          {busy ? "…" : unknown ? "Retry same message" : "➤"}
        </button>
      </div>

      <UploadRecovery queue={uploads.queue} />

      {send.error && (
        <p className="chat__error" role="alert" style={{ padding: "0 16px" }}>
          {send.error}
        </p>
      )}
      {unknown && (
        <p role="status" style={{ padding: "0 16px", fontSize: "12px", color: "var(--warn)" }}>
          Message outcome is unconfirmed. Retry the same message; its text and thread are kept unchanged.
        </p>
      )}
    </form>
  );
}
