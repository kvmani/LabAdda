import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { api, errorMessage, outcomeUnknown } from "../api";
import { useTaskUpdates } from "../taskUpdates";

type Comment = {
  id: string;
  sequence: number;
  body: string;
  created_at: string;
  author: { id: string; display_name: string };
};
type Page = { items: Comment[]; next_cursor: number | null };
export function TaskComments({
  listId,
  taskId,
  writable,
  workspaceId,
}: {
  listId: string;
  taskId: string;
  writable: boolean;
  workspaceId?: string;
}) {
  const [open, setOpen] = useState(false),
    [page, setPage] = useState<Page | null>(null),
    [text, setText] = useState("");
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [busy, setBusy] = useState(false),
    [unconfirmed, setUnconfirmed] = useState(false);
  const generation = useRef(0),
    attempt = useRef<{ client_id: string; body: string } | null>(null);
  const path = `/todos/lists/${listId}/tasks/${taskId}/comments`;
  useEffect(() => {
    return () => {
      invalidate(generation);
    };
  }, [listId, taskId]);
  const updates = useTaskUpdates(open && workspaceId ? [workspaceId] : [], () => {
    ++generation.current;
    setPage(null);
    setOpen(false);
    setText("");
    attempt.current = null;
    setUnconfirmed(false);
    setBusy(false);
    setLoading(false);
  });
  async function load(before?: number) {
    const seen = updates.snapshot();
    const token = ++generation.current;
    setOpen(true);
    setPage(null);
    setError("");
    setLoading(true);
    try {
      const result = await api<Page>(path, { params: { before } });
      if (token === generation.current) {
        setPage(result);
        if (before === undefined) updates.acknowledge(seen);
      }
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const token = ++generation.current;
    setBusy(true);
    setError("");
    setLoading(false);
    try {
      attempt.current ??= { client_id: crypto.randomUUID(), body: text };
      await api(path, { body: attempt.current });
      if (token !== generation.current) return;
      setText("");
      attempt.current = null;
      setUnconfirmed(false);
      setBusy(false);
      await load();
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        const unknown = outcomeUnknown(e);
        setUnconfirmed(unknown);
        if (!unknown) attempt.current = null;
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  if (!open)
    return (
      <button type="button" onClick={() => load()}>
        View comments
      </button>
    );
  return (
    <section aria-label="Task comments">
      <h5>Comments</h5>
      <p>Refresh comments to see new discussion.</p>
      {workspaceId && updates.pending && (
        <p role="status">Shared discussion may have changed. Refresh comments; your draft is kept.</p>
      )}
      <button type="button" disabled={busy} onClick={() => load()}>
        Refresh comments
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          ++generation.current;
          setOpen(false);
          setPage(null);
        }}
      >
        Close comments
      </button>
      {loading && <p role="status">Loading comments…</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {page &&
        (page.items.length === 0 ? (
          <p>No comments yet.</p>
        ) : (
          <ol>
            {page.items.map((comment) => (
              <li key={comment.id} data-comment-sequence={comment.sequence}>
                <p>
                  <strong>{comment.author.display_name}</strong> ·{" "}
                  {new Date(comment.created_at).toLocaleString()}
                </p>
                <p className="preserve">{comment.body}</p>
              </li>
            ))}
          </ol>
        ))}
      {page?.next_cursor && (
        <button type="button" disabled={busy} onClick={() => load(page.next_cursor!)}>
          Older comments
        </button>
      )}
      {writable && (
        <form onSubmit={submit}>
          <label>
            New task comment
            <textarea
              aria-label="New task comment"
              required
              maxLength={4000}
              value={text}
              disabled={busy || unconfirmed}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          {unconfirmed && (
            <p role="status">
              Comment creation is unconfirmed. Retry the same request to recover it; the original text is kept
              unchanged.
            </p>
          )}
          <button type="submit" disabled={busy}>
            {busy ? "Posting…" : unconfirmed ? "Retry same comment" : "Post comment"}
          </button>
        </form>
      )}
      {!writable && <p>This task is read-only.</p>}
    </section>
  );
}
