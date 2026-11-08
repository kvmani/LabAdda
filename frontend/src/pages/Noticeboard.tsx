import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, newId } from "../api";
import { fmtTime, localToIso } from "../format";
import { realtime } from "../realtime";
import { useSession } from "../session";
import type { Attachment, Post, Workspace } from "../types";
import { UploadRecovery, useUploadQueue } from "../components/UploadRecovery";

type Feed = { pinned: Post[]; posts: Post[]; next_before: number | null };
type Upcoming = { id: string; title: string; due_at: string; kind?: string };

function Attachments({ items }: { items: Attachment[] }) {
  if (!items.length) return null;
  return (
    <ul className="attachments">
      {items.map((a) => (
        <li key={a.id}>
          {a.preview_url ? (
            <a href={a.url} target="_blank" rel="noopener"><img src={a.preview_url} alt={a.display_name} loading="lazy" /></a>
          ) : (
            <a href={a.url}>📄 {a.display_name}</a>
          )}
          <span className="muted small"> {a.size < 1024 ? `${a.size} B` : `${Math.round(a.size / 1024)} KiB`}</span>
        </li>
      ))}
    </ul>
  );
}

function PostCard({ post, ws, onChanged }: { post: Post; ws: Workspace; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
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
    } catch (e: any) {
      setError(e.message);
      return false;
    }
  }

  async function sendReply(e: FormEvent) {
    e.preventDefault();
    if (await run(() => api(`/posts/${post.id}/replies`, { body: { body: reply, client_id: replyId.current } }))) {
      setReply("");
      replyId.current = newId("r");
    }
  }

  async function remove(p: Post) {
    const own = p.can_edit;
    const reason = own ? null : window.prompt("Reason for removing this post (recorded in the audit log):");
    if (!own && !reason) return;
    if (own && !window.confirm("Delete this post?")) return;
    await run(() => api(`/posts/${p.id}`, { method: "DELETE", params: { reason } }));
  }

  return (
    <article className={"post card" + (post.kind === "official" ? " official" : "")} aria-label={`Post by ${post.author?.display_name}`}>
      <header className="row between">
        <div>
          {post.pinned && <span className="tag pin">Pinned</span>}
          {post.kind === "official" && <span className="tag official-tag">Official notice</span>}
          <strong>{post.author?.display_name ?? "Unknown"}</strong>
          {post.author && !post.author.is_active && <span className="muted small"> (former member)</span>}
          <span className="muted small"> · {fmtTime(post.created_at)}{post.edited_at ? " · edited" : ""}</span>
        </div>
        <div className="row">
          {ws.can_moderate && !ws.archived && (
            <button className="ghost small" onClick={() => run(() => api(`/posts/${post.id}/pin`, { body: { pinned: !post.pinned } }))}>
              {post.pinned ? "Unpin" : "Pin"}
            </button>
          )}
          {post.can_edit && ws.can_write && <button className="ghost small" onClick={() => setEditing(true)}>Edit</button>}
          {post.can_remove && <button className="ghost small" onClick={() => remove(post)}>{post.can_edit ? "Delete" : "Remove"}</button>}
        </div>
      </header>
      {editing ? (
        <form onSubmit={async (e) => { e.preventDefault(); if (await run(() => api(`/posts/${post.id}`, { method: "PATCH", body: { body: text } }))) setEditing(false); }}>
          <label className="sr-only" htmlFor={`edit-${post.id}`}>Edit post</label>
          <textarea id={`edit-${post.id}`} value={text} onChange={(e) => setText(e.target.value)} rows={3} />
          <div className="row"><button type="submit">Save</button><button type="button" className="ghost" onClick={() => { setEditing(false); setText(post.body); }}>Cancel</button></div>
        </form>
      ) : (
        <p className="body">{post.body}</p>
      )}
      {post.snapshot && (
        <p className="muted small">
          📷 Board snapshot at revision {post.snapshot.source_revision}
          {post.snapshot.source_name ? <> from <Link to={`/w/${post.snapshot.source_workspace_id}/board`}>{post.snapshot.source_name}</Link></> : ""}. Fixed copy: later board changes do not affect it.
        </p>
      )}
      {post.due_at && <p className="due">Due {fmtTime(post.due_at)}{post.remind_at ? ` · reminder ${fmtTime(post.remind_at)}` : ""}</p>}
      <Attachments items={post.attachments} />
      {post.replies.length > 0 && (
        <ul className="replies">
          {post.replies.map((r) => (
            <li key={r.id}>
              <strong>{r.author?.display_name}</strong> <span className="muted small">{fmtTime(r.created_at)}</span>
              {r.can_remove && <button className="ghost small" onClick={() => remove(r)}>{r.can_edit ? "Delete" : "Remove"}</button>}
              <p className="body">{r.body}</p>
            </li>
          ))}
        </ul>
      )}
      {ws.can_write && (
        <form className="reply-form" onSubmit={sendReply}>
          <label className="sr-only" htmlFor={`reply-${post.id}`}>Reply</label>
          <input id={`reply-${post.id}`} placeholder="Write a reply…" value={reply} onChange={(e) => setReply(e.target.value)} required maxLength={10000} />
          <button type="submit" className="small">Reply</button>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </article>
  );
}

const drafts = new Map<string, string>(); // drafts stay scoped to their original workspace

function Composer({ ws, onPosted }: { ws: Workspace; onPosted: () => void }) {
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
  const uploads = useUploadQueue(limits.max_attachment_bytes, asset => {
    setFiles(prev => prev.some(f => f.id === asset.id) ? prev : [...prev, asset]);
  });

  const setBody = (v: string) => {
    setBodyState(v);
    drafts.set(ws.id, v);
    setSaved(false);
  };

  function addFiles(list: FileList | null) {
    if (!list) return;
    setError(null);
    try { uploads.queue.add(Array.from(list), limits.max_attachments - files.length); }
    catch (e: any) { setError(e.message); }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (uploads.attempts.length) return setError("Resolve or dismiss pending uploads before posting.");
    setBusy(true);
    setError(null);
    try {
      await api(`/workspaces/${ws.id}/posts`, {
        body: { body, kind: official ? "official" : "discussion", due_at: localToIso(due), remind_at: localToIso(remind), attachment_ids: files.map((f) => f.id), client_id: clientId.current },
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
    } catch (e: any) {
      setError(e.message + " Your text is kept so you can try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!ws.can_write) {
    return <p className="notice">{ws.archived ? "This workspace is archived. Content stays readable but no one can post." : "Posting is limited to stewards in this workspace."}</p>;
  }
  return (
    <form className="composer card" onSubmit={submit} aria-label={`Post to ${ws.name}`}>
      <div className="row between">
        <strong>Post to {ws.name}</strong>
        <span className="muted small">Audience: {ws.kind === "group" ? "group members only" : ws.kind === "project" ? "project members only" : `members of ${ws.name} and its sub-units`}</span>
      </div>
      <label className="sr-only" htmlFor="composer-body">Message</label>
      <textarea id="composer-body" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Share an update, @mention a colleague…" rows={3} required maxLength={10000} />
      <div className="row wrap">
        <label className="inline">Due <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} /></label>
        <label className="inline">Remind <input type="datetime-local" value={remind} onChange={(e) => setRemind(e.target.value)} /></label>
        <label className="inline">Attach <input type="file" accept="application/pdf,image/png,image/jpeg" multiple disabled={busy} onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} /></label>
        {ws.can_moderate && <label className="inline"><input type="checkbox" checked={official} onChange={(e) => setOfficial(e.target.checked)} /> Official notice</label>}
      </div>
      {files.length > 0 && (
        <ul className="plain chips">
          {files.map((f) => (
            <li key={f.id} className="chip">{f.display_name}
              <button type="button" className="ghost small" aria-label={`Remove ${f.display_name}`} onClick={() => { api(`/uploads/${f.id}`, { method: "DELETE" }).catch(() => undefined); setFiles(files.filter((x) => x.id !== f.id)); }}>×</button>
            </li>
          ))}
        </ul>
      )}
      <UploadRecovery queue={uploads.queue} />
      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button type="submit" disabled={busy || uploads.attempts.length > 0}>{busy ? "Posting…" : "Post"}</button>
        {saved && <span className="ok" role="status">Posted</span>}
      </div>
    </form>
  );
}

export function Noticeboard({ ws }: { ws: Workspace }) {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<Upcoming[]>([]);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any | null>(null);

  const load = useCallback(async () => {
    try {
      const [f, u] = await Promise.all([api<Feed>(`/workspaces/${ws.id}/posts`), api(`/workspaces/${ws.id}/upcoming`)]);
      setFeed(f);
      setUpcoming(u.items);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, [ws.id]);

  useEffect(() => {
    load();
    return realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "noticeboard.changed" || ev.type === "subscribed") load();
    });
  }, [load, ws.id]);

  async function more() {
    if (!feed?.next_before) return;
    const next = await api<Feed>(`/workspaces/${ws.id}/posts`, { params: { before: feed.next_before } });
    setFeed({ ...feed, posts: [...feed.posts, ...next.posts], next_before: next.next_before });
  }

  async function search(e: FormEvent) {
    e.preventDefault();
    if (query.trim().length < 2) return setResults(null);
    try {
      setResults(await api(`/workspaces/${ws.id}/search`, { params: { q: query.trim() } }));
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <div className="board-layout">
      <section className="feed" aria-label="Noticeboard feed">
        <Composer ws={ws} onPosted={load} />
        {error && <p className="error" role="alert">{error} <button className="ghost small" onClick={load}>Retry</button></p>}
        {!feed ? <p className="muted">Loading posts…</p> : feed.pinned.length + feed.posts.length === 0 ? (
          <p className="state empty">No posts yet in {ws.name}.{ws.can_write ? " Start the conversation above." : ""}</p>
        ) : (
          <>
            {feed.pinned.map((p) => <PostCard key={p.id} post={p} ws={ws} onChanged={load} />)}
            {feed.posts.map((p) => <PostCard key={p.id} post={p} ws={ws} onChanged={load} />)}
            {feed.next_before && <button className="ghost" onClick={more}>Load older posts</button>}
          </>
        )}
      </section>
      <aside className="secondary" aria-label="Upcoming and search">
        <section className="card">
          <h2>Upcoming</h2>
          {upcoming.length === 0 ? <p className="muted small">Nothing scheduled.</p> : (
            <ul className="plain">{upcoming.map((u) => <li key={u.id}><strong>{fmtTime(u.due_at)}</strong><br />{u.title}</li>)}</ul>
          )}
        </section>
        <section className="card">
          <h2>Search {ws.name}</h2>
          <form onSubmit={search} className="row">
            <label className="sr-only" htmlFor="ws-search">Search this workspace</label>
            <input id="ws-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Posts and chat" />
            <button type="submit" className="small">Search</button>
          </form>
          {results && (
            <div className="small">
              <p className="muted">{results.counts.posts} posts · {results.counts.chat} chat messages</p>
              <ul className="plain">
                {results.posts.map((p: any) => <li key={p.id}>📝 {p.body}</li>)}
                {results.chat.map((c: any) => <li key={c.id}>💬 {c.author?.display_name}: {c.body}</li>)}
              </ul>
            </div>
          )}
        </section>
        <section className="card">
          <h2>Whiteboard</h2>
          <Link to={`/w/${ws.id}/board`}>Open the live board</Link>
        </section>
      </aside>
    </div>
  );
}
