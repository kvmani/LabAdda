import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ChatFiles } from "../components/ChatFiles";
import { ChatComposer } from "../components/ChatComposer";
import { ChatThread } from "../components/ChatThread";
import { ConversationTask } from "../components/ConversationTask";
import { api, newId } from "../api";
import { fmtTime } from "../format";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";
import type { ChatMessage, Workspace } from "../types";

export function Chat({ ws }: { ws: Workspace }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]),
    [hasMore, setHasMore] = useState(false),
    [moreNew, setMoreNew] = useState(false);
  const [earlier, setEarlier] = useState(false);
  const historyMode = useRef(false),
    resetLatest = useRef(false),
    viewGeneration = useRef(0);
  const [error, setError] = useState(""),
    [blocked, setBlocked] = useState(false),
    [summary, setSummary] = useState<string | null>(null),
    [taskSource, setTaskSource] = useState<ChatMessage | null>(null),
    [thread, setThread] = useState<string | null>(null);
  const safeCursor = useRef(0),
    generation = useRef(0),
    catching = useRef(false),
    queued = useRef(false),
    refreshTimer = useRef<number | undefined>(undefined),
    listRef = useRef<HTMLOListElement>(null);
  const { reload } = useWorkspaces();
  function deny() {
    ++generation.current;
    setBlocked(true);
    setMessages([]);
    setHasMore(false);
    setMoreNew(false);
    setSummary(null);
    setTaskSource(null);
    setThread(null);
  }
  const merge = useCallback(
    (incoming: ChatMessage[], older = false) =>
      setMessages((previous) => {
        const byId = new Map(previous.map((m) => [m.id, m]));
        incoming.forEach((m) => byId.set(m.id, m));
        const all = [...byId.values()].sort((a, b) => a.seq - b.seq);
        return older ? all.slice(0, 500) : all.slice(-500);
      }),
    [],
  );
  const catchUp = useCallback(async () => {
    if (catching.current) {
      queued.current = true;
      return;
    }
    catching.current = true;
    if (resetLatest.current) {
      resetLatest.current = false;
      safeCursor.current = 0;
      setMessages([]);
    }
    const token = generation.current;
    try {
      for (let i = 0; i < 4; i++) {
        const cursor = safeCursor.current;
        const result = await api(`/workspaces/${ws.id}/chat`, {
          params: cursor ? { after: cursor, limit: 200 } : { limit: 50 },
        });
        if (token !== generation.current) return;
        if (!historyMode.current) merge(result.messages);
        if (!cursor) setHasMore(result.has_more);
        // Only an authorized HTTP snapshot advances replay state. Live high sequence
        // display must never hide a committed message whose fanout was interrupted.
        if (result.messages.length)
          safeCursor.current = Math.max(cursor, ...result.messages.map((m: ChatMessage) => m.seq));
        if (!historyMode.current) setMoreNew(!!cursor && result.has_more);
        else if (result.messages.length) setMoreNew(true);
        if (!cursor || !result.has_more) break;
      }
      if (token !== generation.current) return;
      if (!historyMode.current)
        await api(`/workspaces/${ws.id}/chat/read`, { body: { seq: safeCursor.current } });
      if (token === generation.current) {
        setError("");
        reload();
      }
    } catch (e: any) {
      if (token === generation.current) {
        setError(e.message);
        if ([401, 403, 404].includes(e.status)) deny();
      }
    } finally {
      catching.current = false;
      if (queued.current && token === generation.current) {
        queued.current = false;
        queueMicrotask(() => catchUp());
      }
    }
  }, [ws.id, merge, reload]);
  useEffect(() => {
    let active = true;
    catchUp();
    const stop = realtime.subscribe(ws.id, (event) => {
      if (!active) return;
      if (event.type === "chat.message") {
        if (historyMode.current) setMoreNew(true);
        else merge([event.message]);
        if (refreshTimer.current === undefined)
          refreshTimer.current = window.setTimeout(() => {
            refreshTimer.current = undefined;
            catchUp();
          }, 150);
      }
      if (event.type === "subscribed") catchUp();
      if (["revoked", "subscribe_failed", "session_ended"].includes(event.type)) deny();
    });
    return () => {
      active = false;
      ++generation.current;
      window.clearTimeout(refreshTimer.current);
      queued.current = false;
      stop();
    };
  }, [ws.id, catchUp, merge]);
  useEffect(() => {
    if (!thread) listRef.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [messages.length, thread]);
  async function older() {
    const token = generation.current,
      view = ++viewGeneration.current,
      first = messages[0];
    if (!first) return;
    historyMode.current = true;
    setEarlier(true);
    try {
      const result = await api(`/workspaces/${ws.id}/chat`, { params: { before: first.seq } });
      if (token === generation.current && view === viewGeneration.current && historyMode.current) {
        setHasMore(result.has_more);
        setMessages(result.messages);
      }
    } catch (e: any) {
      if (token === generation.current) {
        setError(e.message);
        if ([401, 403, 404].includes(e.status)) deny();
      }
    }
  }
  function latest() {
    ++viewGeneration.current;
    historyMode.current = false;
    setEarlier(false);
    resetLatest.current = true;
    catchUp();
  }
  return (
    <>
      <section className="chat card" aria-label={`Chat in ${ws.name}`}>
        {blocked ? (
          <p role="alert">This chat is no longer available.</p>
        ) : (
          <>
            <button type="button" onClick={latest}>
              Refresh chat
            </button>
            {earlier && (
              <p>
                Viewing earlier messages.{" "}
                <button type="button" onClick={latest}>
                  Return to latest messages
                </button>
              </p>
            )}
            {hasMore && (
              <button type="button" onClick={older}>
                Load earlier messages
              </button>
            )}
            {moreNew && (
              <button type="button" onClick={earlier ? latest : catchUp}>
                Load more new messages
              </button>
            )}
            <ol className="messages" ref={listRef} aria-live="polite">
              {messages.length === 0 && <li>No messages yet.</li>}
              {messages.map((message) => (
                <li key={message.id}>
                  <strong>{message.author?.display_name}</strong>{" "}
                  <span className="muted small">{fmtTime(message.created_at)}</span>
                  {message.parent_id && <span className="tag">Thread reply</span>}
                  <button
                    type="button"
                    className="ghost small"
                    onClick={() => setThread(message.parent_id ?? message.id)}
                  >
                    Open thread
                  </button>
                  <button
                    type="button"
                    className="ghost small"
                    onClick={() =>
                      setSummary(
                        `Chat summary from ${ws.name}:\n> ${message.author?.display_name}: ${message.body}`,
                      )
                    }
                    aria-label="Publish to noticeboard"
                  >
                    Share to noticeboard
                  </button>
                  <button type="button" className="ghost small" onClick={() => setTaskSource(message)}>
                    Create task
                  </button>
                  <p className="body">{message.body}</p>
                  <ChatFiles files={message.attachments} />
                </li>
              ))}
            </ol>
            {error && (
              <p role="alert" className="error">
                {error}
              </p>
            )}
            <ChatComposer ws={ws} sent={(message) => merge([message])} denied={deny} />
            {taskSource && (
              <ConversationTask
                key={taskSource.id}
                source={ws}
                kind="chat"
                sourceId={taskSource.id}
                text={taskSource.body}
                close={() => setTaskSource(null)}
              />
            )}
            {summary !== null && (
              <PublishSummary source={ws} text={summary} onClose={() => setSummary(null)} />
            )}
          </>
        )}
      </section>
      {!blocked && thread && (
        <ChatThread key={thread} ws={ws} rootId={thread} close={() => setThread(null)} />
      )}
    </>
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
      <label>
        Destination
        <select
          value={dest}
          onChange={(e) => {
            setDest(e.target.value);
            setConfirmed(false);
          }}
        >
          {targets.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Summary
        <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} />
      </label>
      {broader && (
        <label className="warning">
          <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} /> I
          understand this copy will be visible to everyone who can read <strong>{target?.name}</strong>, a
          different audience from {source.name}.
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit" disabled={broader && !confirmed}>
          Post to {target?.name}
        </button>
        <button type="button" className="ghost" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}
