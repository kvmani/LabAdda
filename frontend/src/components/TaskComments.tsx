import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { Button, TextArea } from "../ui";
import "./task.css";
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
type CommentsProps = { listId: string; taskId: string; writable: boolean; workspaceId?: string };

/** Comment panel state; a draft is kept, and a retry reuses one client id until the outcome is known. */
function useTaskComments({ listId, taskId, workspaceId }: CommentsProps) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<Page | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const generation = useRef(0);
  const attempt = useRef<{ client_id: string; body: string } | null>(null);
  const path = `/todos/lists/${listId}/tasks/${taskId}/comments`;

  useEffect(() => {
    return () => {
      invalidate(generation);
    };
  }, [listId, taskId]);

  const updates = useTaskUpdates(open && workspaceId ? [workspaceId] : [], () => {
    generation.current += 1;
    setPage(null);
    setOpen(false);
    setText("");
    attempt.current = null;
    setUnconfirmed(false);
    setBusy(false);
    setLoading(false);
  });

  async function load(before?: number) {
    const seenVersion = updates.snapshot();
    generation.current += 1;
    const token = generation.current;
    setOpen(true);
    setPage(null);
    setError("");
    setLoading(true);
    try {
      const result = await api<Page>(path, { params: { before } });
      if (token === generation.current) {
        setPage(result);
        if (before === undefined) updates.acknowledge(seenVersion);
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
    generation.current += 1;
    const token = generation.current;
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

  function close() {
    generation.current += 1;
    setOpen(false);
    setPage(null);
  }

  return { open, page, text, setText, error, loading, busy, unconfirmed, updates, load, submit, close };
}

function CommentList({ page }: { page: Page }) {
  if (page.items.length === 0) return <p>No comments yet.</p>;
  return (
    <ol>
      {page.items.map((comment) => (
        <li key={comment.id} data-comment-sequence={comment.sequence}>
          <p>
            <strong>{comment.author.display_name}</strong> · {new Date(comment.created_at).toLocaleString()}
          </p>
          <p className="task__text">{comment.body}</p>
        </li>
      ))}
    </ol>
  );
}

function CommentForm({ comments }: { comments: ReturnType<typeof useTaskComments> }) {
  const { busy, unconfirmed, text } = comments;
  return (
    <form onSubmit={comments.submit}>
      <TextArea
        label="New task comment"
        maxLength={4000}
        value={text}
        disabled={busy || unconfirmed}
        onChange={(e) => comments.setText(e.target.value)}
      />
      {unconfirmed && (
        <p role="status">
          Comment creation is unconfirmed. Retry the same request to recover it; the original text is kept
          unchanged.
        </p>
      )}
      <Button size="sm" variant="primary" type="submit" disabled={busy || !text.trim()}>
        {busy ? "Posting…" : unconfirmed ? "Retry same comment" : "Post comment"}
      </Button>
    </form>
  );
}

export function TaskComments(props: CommentsProps) {
  const { writable, workspaceId } = props;
  const comments = useTaskComments(props);
  const { page, busy } = comments;
  if (!comments.open) {
    return (
      <Button size="sm" onClick={() => comments.load()}>
        View comments
      </Button>
    );
  }
  return (
    <section className="task-panel" aria-label="Task comments">
      <h5>Comments</h5>
      <p>Refresh comments to see new discussion.</p>
      {workspaceId && comments.updates.pending && (
        <p role="status">Shared discussion may have changed. Refresh comments; your draft is kept.</p>
      )}
      <Button size="sm" disabled={busy} onClick={() => comments.load()}>
        Refresh comments
      </Button>
      <Button size="sm" disabled={busy} onClick={comments.close}>
        Close comments
      </Button>
      {comments.loading && <p role="status">Loading comments…</p>}
      {comments.error && (
        <p className="task__error" role="alert">
          {comments.error}
        </p>
      )}
      {page && <CommentList page={page} />}
      {page?.next_cursor && (
        <Button size="sm" disabled={busy} onClick={() => comments.load(page.next_cursor!)}>
          Older comments
        </Button>
      )}
      {writable && <CommentForm comments={comments} />}
      {!writable && <p>This task is read-only.</p>}
    </section>
  );
}
