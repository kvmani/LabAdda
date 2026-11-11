import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, newId, errorMessage } from "../api";
import { fmtTime } from "../format";
import type { Attachment, Post, Workspace } from "../types";
import { Button, Card, ConfirmDialog, Tag, TextArea, TextInput } from "../ui";
import { ConversationTask } from "./ConversationTask";
import "./post-card.css";

function Attachments({ items }: { items: Attachment[] }) {
  if (!items.length) return null;
  return (
    <ul className="attachments">
      {items.map((a) => (
        <li key={a.id}>
          {a.preview_url ? (
            <a href={a.url} target="_blank" rel="noopener">
              <img src={a.preview_url} alt={a.display_name} loading="lazy" />
            </a>
          ) : (
            <a href={a.url}>📄 {a.display_name}</a>
          )}
          <span className="post-card__meta">
            {" "}
            {a.size < 1024 ? `${a.size} B` : `${Math.round(a.size / 1024)} KiB`}
          </span>
        </li>
      ))}
    </ul>
  );
}

type Removal = { id: string; own: boolean; isReply: boolean };

export function PostCard({ post, ws, onChanged }: { post: Post; ws: Workspace; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [removal, setRemoval] = useState<Removal | null>(null);
  const [text, setText] = useState(post.body);
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const replyId = useRef(newId("r"));

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      onChanged();
      return true;
    } catch (e: unknown) {
      setError(errorMessage(e));
      return false;
    }
  }

  async function sendReply(e: FormEvent) {
    e.preventDefault();
    if (
      await run(() => api(`/posts/${post.id}/replies`, { body: { body: reply, client_id: replyId.current } }))
    ) {
      setReply("");
      replyId.current = newId("r");
    }
  }

  async function confirmRemoval(reason: string) {
    if (!removal) return;
    await api(`/posts/${removal.id}`, { method: "DELETE", params: { reason: removal.own ? null : reason } });
    setRemoval(null);
    onChanged();
  }

  const removeLabel = (own: boolean) => (own ? "Delete" : "Remove");
  const removing = removal?.isReply ? "reply" : "post";

  return (
    <article
      className={"post" + (post.kind === "official" ? " post--official" : "")}
      aria-label={`Post by ${post.author?.display_name}`}
    >
      <Card>
        <header className="post-card__header">
          <div className="post-card__byline">
            {post.pinned && <Tag tone="info">Pinned</Tag>}
            {post.kind === "official" && <Tag tone="warn">Official notice</Tag>}
            <strong>{post.author?.display_name ?? "Unknown"}</strong>
            {post.author && !post.author.is_active && (
              <span className="post-card__meta"> (former member)</span>
            )}
            <span className="post-card__meta">
              {" "}
              · {fmtTime(post.created_at)}
              {post.edited_at ? " · edited" : ""}
            </span>
          </div>
          <div className="post-card__actions">
            {ws.can_moderate && !ws.archived && (
              <Button
                variant="quiet"
                size="sm"
                onClick={() => run(() => api(`/posts/${post.id}/pin`, { body: { pinned: !post.pinned } }))}
              >
                {post.pinned ? "Unpin" : "Pin"}
              </Button>
            )}
            {post.can_edit && ws.can_write && (
              <Button variant="quiet" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {post.can_remove && (
              <Button
                variant="quiet"
                size="sm"
                onClick={() => setRemoval({ id: post.id, own: post.can_edit, isReply: false })}
              >
                {removeLabel(post.can_edit)}
              </Button>
            )}
          </div>
        </header>
        {editing ? (
          <form
            className="post-card__form"
            onSubmit={async (e) => {
              e.preventDefault();
              if (await run(() => api(`/posts/${post.id}`, { method: "PATCH", body: { body: text } })))
                setEditing(false);
            }}
          >
            <TextArea label="Edit post" value={text} onChange={(e) => setText(e.target.value)} rows={3} />
            <div className="post-card__actions">
              <Button variant="primary" type="submit">
                Save
              </Button>
              <Button
                variant="quiet"
                onClick={() => {
                  setEditing(false);
                  setText(post.body);
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <p className="post-card__body">{post.body}</p>
        )}
        <div>
          <Button variant="quiet" size="sm" onClick={() => setTaskOpen(true)}>
            Create task
          </Button>
        </div>
        {taskOpen && (
          <ConversationTask
            source={ws}
            kind="post"
            sourceId={post.id}
            text={post.body}
            close={() => setTaskOpen(false)}
          />
        )}
        {post.snapshot && (
          <p className="post-card__meta">
            📷 Board snapshot at revision {post.snapshot.source_revision}
            {post.snapshot.source_name ? (
              <>
                {" "}
                from{" "}
                <Link to={`/w/${post.snapshot.source_workspace_id}/board`}>{post.snapshot.source_name}</Link>
              </>
            ) : (
              ""
            )}
            . Fixed copy: later board changes do not affect it.
          </p>
        )}
        {post.due_at && (
          <p className="post-card__due">
            Due {fmtTime(post.due_at)}
            {post.remind_at ? ` · reminder ${fmtTime(post.remind_at)}` : ""}
          </p>
        )}
        <Attachments items={post.attachments} />
        {post.replies.length > 0 && (
          <ul className="post-card__replies">
            {post.replies.map((r) => (
              <li key={r.id}>
                <strong>{r.author?.display_name}</strong>{" "}
                <span className="post-card__meta">{fmtTime(r.created_at)}</span>
                {r.can_remove && (
                  <Button
                    variant="quiet"
                    size="sm"
                    onClick={() => setRemoval({ id: r.id, own: r.can_edit, isReply: true })}
                  >
                    {removeLabel(r.can_edit)}
                  </Button>
                )}
                <p className="post-card__body">{r.body}</p>
              </li>
            ))}
          </ul>
        )}
        {ws.can_write && (
          <form className="post-card__reply" onSubmit={sendReply}>
            <TextInput
              label="Reply"
              placeholder="Write a reply…"
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              required
              maxLength={10000}
            />
            <Button type="submit" size="sm">
              Reply
            </Button>
          </form>
        )}
        {error && (
          <p className="post-card__error" role="alert">
            {error}
          </p>
        )}
      </Card>
      <ConfirmDialog
        open={removal !== null}
        title={`${removeLabel(removal?.own ?? false)} this ${removing}`}
        consequences={
          removal?.own
            ? [`The ${removing} is hidden from everyone in ${ws.name}.`]
            : [
                `The ${removing} is hidden from everyone in ${ws.name}.`,
                "Your reason is recorded in the audit log.",
              ]
        }
        confirmLabel={`${removeLabel(removal?.own ?? false)} ${removing}`}
        requireReason={removal ? !removal.own : false}
        onConfirm={confirmRemoval}
        onCancel={() => setRemoval(null)}
        danger
      />
    </article>
  );
}
