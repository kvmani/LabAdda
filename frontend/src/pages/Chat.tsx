import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, newId } from "../api";
import { fmtTime } from "../format";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";
import type { ChatMessage, Workspace } from "../types";

type Pending = { client_id: string; body: string; failed?: boolean };

export function Chat({ ws }: { ws: Workspace }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [pending, setPending] = useState<Pending[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const lastSeq = useRef(0);
  const listRef = useRef<HTMLOListElement>(null);
  const { reload } = useWorkspaces();

  const merge = useCallback((incoming: ChatMessage[]) => {
    setMessages((prev) => {
      const seen = new Map(prev.map((m) => [m.seq, m]));
      incoming.forEach((m) => seen.set(m.seq, m));
      const all = [...seen.values()].sort((a, b) => a.seq - b.seq);
      lastSeq.current = all.length ? all[all.length - 1].seq : lastSeq.current;
      return all;
    });
    setPending((p) => p.filter((x) => !incoming.some((m) => m.client_id === x.client_id)));
  }, []);

  const catchUp = useCallback(async () => {
    try {
      const r = await api(`/workspaces/${ws.id}/chat`, { params: lastSeq.current ? { after: lastSeq.current, limit: 200 } : { limit: 50 } });
      if (!lastSeq.current) setHasMore(r.has_more);
      merge(r.messages);
      if (lastSeq.current) {
        await api(`/workspaces/${ws.id}/chat/read`, { body: { seq: lastSeq.current } });
        reload();
      }
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, [ws.id, merge, reload]);

  useEffect(() => {
    catchUp();
    return realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "chat.message") {
        merge([ev.message]);
        api(`/workspaces/${ws.id}/chat/read`, { body: { seq: ev.message.seq } }).catch(() => undefined);
      }
      if (ev.type === "subscribed") catchUp(); // replay anything missed while disconnected
    });
  }, [ws.id, catchUp, merge]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [messages.length, pending.length]);

  async function send(p: Pending) {
    setPending((prev) => [...prev.filter((x) => x.client_id !== p.client_id), { ...p, failed: false }]);
    try {
      const m = await api<ChatMessage>(`/workspaces/${ws.id}/chat`, { body: { body: p.body, client_id: p.client_id } });
      merge([m]);
    } catch (e: any) {
      setError(e.message);
      setPending((prev) => prev.map((x) => (x.client_id === p.client_id ? { ...x, failed: true } : x)));
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    send({ client_id: newId("m"), body: text });
    setText("");
  }

  async function older() {
    const first = messages[0];
    if (!first) return;
    const r = await api(`/workspaces/${ws.id}/chat`, { params: { before: first.seq } });
    setHasMore(r.has_more);
    merge(r.messages);
  }

  return (
    <section className="chat card" aria-label={`Chat in ${ws.name}`}>
      {hasMore && <button className="ghost small" onClick={older}>Load earlier messages</button>}
      <ol className="messages" ref={listRef} aria-live="polite">
        {messages.length === 0 && pending.length === 0 && <li className="muted">No messages yet.</li>}
        {messages.map((m) => (
          <li key={m.seq}>
            <strong>{m.author?.display_name}</strong> <span className="muted small">{fmtTime(m.created_at)}</span>
            <button className="ghost small" onClick={() => setSummary(`Chat summary from ${ws.name}:\n> ${m.author?.display_name}: ${m.body}`)} aria-label="Publish to noticeboard">Share to noticeboard</button>
            <p className="body">{m.body}</p>
          </li>
        ))}
        {pending.map((p) => (
          <li key={p.client_id} className="pending">
            <span className="muted small">{p.failed ? "Not sent" : "Sending…"}</span>
            <p className="body">{p.body}</p>
            {p.failed && <button className="small" onClick={() => send(p)}>Retry</button>}
          </li>
        ))}
      </ol>
      {error && <p className="error" role="alert">{error}</p>}
      {ws.can_write ? (
        <form className="row" onSubmit={submit}>
          <label className="sr-only" htmlFor="chat-input">Message {ws.name}</label>
          <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={`Message ${ws.name}`} maxLength={4000} autoComplete="off" />
          <button type="submit">Send</button>
        </form>
      ) : (
        <p className="notice">Chat is read-only here.</p>
      )}
      {summary !== null && <PublishSummary source={ws} text={summary} onClose={() => setSummary(null)} />}
    </section>
  );
}

function PublishSummary({ source, text, onClose }: { source: Workspace; text: string; onClose: () => void }) {
  const { workspaces } = useWorkspaces();
  const targets = workspaces.filter((w) => w.can_write);
  const [dest, setDest] = useState(source.id);
  const [body, setBody] = useState(text);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const clientId = useRef(newId("s"));
  const target = workspaces.find((w) => w.id === dest);
  const broader = dest !== source.id;

  async function publish(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/workspaces/${dest}/posts`, { body: { body, client_id: clientId.current } });
      onClose();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <form className="dialog card" onSubmit={publish} aria-label="Publish chat summary">
      <h2>Publish summary to a noticeboard</h2>
      <label>Destination
        <select value={dest} onChange={(e) => { setDest(e.target.value); setConfirmed(false); }}>
          {targets.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      </label>
      <label>Summary<textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} /></label>
      {broader && (
        <label className="warning">
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I understand this copy will be visible to everyone who can read <strong>{target?.name}</strong>, a different audience from {source.name}.
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit" disabled={broader && !confirmed}>Post to {target?.name}</button>
        <button type="button" className="ghost" onClick={onClose}>Cancel</button>
      </div>
    </form>
  );
}
