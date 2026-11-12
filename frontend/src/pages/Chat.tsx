import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { ChatFiles } from "../components/ChatFiles";
import { ChatComposer } from "../components/ChatComposer";
import { ChatThread } from "../components/ChatThread";
import { ConversationTask } from "../components/ConversationTask";
import { accessDenied, api, errorMessage, newId } from "../api";
import { fmtTime } from "../format";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";
import type { ChatMessage, ChatPage, Workspace } from "../types";
import { Button, Card, Checkbox, Dialog, EmptyState, Select, Tag, TextArea } from "../ui";
import "../components/chat.css";

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
        const result = await api<ChatPage>(`/workspaces/${ws.id}/chat`, {
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
        void reload();
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (accessDenied(e)) deny();
      }
    } finally {
      catching.current = false;
      if (queued.current && token === generation.current) {
        queued.current = false;
        queueMicrotask(() => void catchUp());
      }
    }
  }, [ws.id, merge, reload]);
  useEffect(() => {
    let active = true;
    void catchUp();
    const stop = realtime.subscribe(ws.id, (event) => {
      if (!active) return;
      if (event.type === "chat.message") {
        if (historyMode.current) setMoreNew(true);
        else merge([event.message]);
        if (refreshTimer.current === undefined)
          refreshTimer.current = window.setTimeout(() => {
            refreshTimer.current = undefined;
            void catchUp();
          }, 150);
      }
      if (event.type === "subscribed") void catchUp();
      if (["revoked", "subscribe_failed", "session_ended"].includes(event.type)) deny();
    });
    return () => {
      active = false;
      invalidate(generation);
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
      const result = await api<ChatPage>(`/workspaces/${ws.id}/chat`, { params: { before: first.seq } });
      if (token === generation.current && view === viewGeneration.current && historyMode.current) {
        setHasMore(result.has_more);
        setMessages(result.messages);
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (accessDenied(e)) deny();
      }
    }
  }
  function latest() {
    ++viewGeneration.current;
    historyMode.current = false;
    setEarlier(false);
    resetLatest.current = true;
    void catchUp();
  }
  return (
    <>
      <section className="chat" aria-label={`Chat in ${ws.name}`}>
        <Card>
          {blocked ? (
            <p role="alert">This chat is no longer available.</p>
          ) : (
            <div className="chat__panel">
              <div className="chat__toolbar">
                <Button icon="refresh" onClick={latest}>
                  Refresh chat
                </Button>
                {hasMore && <Button onClick={older}>Load earlier messages</Button>}
                {moreNew && <Button onClick={earlier ? latest : catchUp}>Load more new messages</Button>}
              </div>
              {earlier && (
                <p className="chat__notice">
                  Viewing earlier messages.{" "}
                  <Button variant="quiet" size="sm" onClick={latest}>
                    Return to latest messages
                  </Button>
                </p>
              )}
              {messages.length === 0 && (
                <EmptyState title="No messages yet.">
                  {ws.can_write ? "Write the first message below." : "Messages will appear here."}
                </EmptyState>
              )}
              <ol className="messages chat__list" ref={listRef} aria-live="polite">
                {messages.map((message) => (
                  <li key={message.id}>
                    <div className="chat__byline">
                      <strong>{message.author?.display_name}</strong>
                      <span className="chat__meta">{fmtTime(message.created_at)}</span>
                      {message.parent_id && <Tag>Thread reply</Tag>}
                    </div>
                    <p className="chat__text">{message.body}</p>
                    <ChatFiles files={message.attachments} />
                    <div className="chat__actions">
                      <Button
                        variant="quiet"
                        size="sm"
                        onClick={() => setThread(message.parent_id ?? message.id)}
                      >
                        Open thread
                      </Button>
                      <Button
                        variant="quiet"
                        size="sm"
                        onClick={() =>
                          setSummary(
                            `Chat summary from ${ws.name}:\n> ${message.author?.display_name}: ${message.body}`,
                          )
                        }
                        aria-label="Publish to noticeboard"
                      >
                        Share to noticeboard
                      </Button>
                      <Button variant="quiet" size="sm" onClick={() => setTaskSource(message)}>
                        Create task
                      </Button>
                    </div>
                  </li>
                ))}
              </ol>
              {error && (
                <p role="alert" className="chat__error">
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
            </div>
          )}
        </Card>
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
  const formId = useId();
  const target = workspaces.find((w) => w.id === dest);
  const broader = dest !== source.id;

  async function publish(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/workspaces/${dest}/posts`, { body: { body, client_id: clientId.current } });
      onClose();
    } catch (err: unknown) {
      setError(errorMessage(err));
    }
  }

  return (
    <Dialog
      open
      title="Publish summary to a noticeboard"
      onClose={onClose}
      footer={
        <>
          <Button variant="quiet" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form={formId} disabled={(broader && !confirmed) || !target}>
            Post to {target?.name}
          </Button>
        </>
      }
    >
      <form id={formId} className="chat__form" onSubmit={publish} aria-label="Publish chat summary">
        <Select
          label="Destination"
          value={dest}
          onChange={(e) => {
            setDest(e.target.value);
            setConfirmed(false);
          }}
          options={targets.map((w) => ({ value: w.id, label: w.name }))}
        />
        <TextArea label="Summary" value={body} onChange={(e) => setBody(e.target.value)} rows={4} />
        {broader && (
          <Checkbox
            label={`I understand this copy will be visible to everyone who can read ${target?.name}, a different audience from ${source.name}.`}
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
        )}
        {error && (
          <p className="chat__error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
