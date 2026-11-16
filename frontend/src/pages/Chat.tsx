import { useCallback, useEffect, useId, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { ChatFiles } from "../components/ChatFiles";
import { ChatComposer } from "../components/ChatComposer";
import { ChatThread } from "../components/ChatThread";
import { ConversationTask } from "../components/ConversationTask";
import { accessDenied, api, errorMessage, newId } from "../api";
import { fmtClockTimeIST, fmtDateBadgeIST } from "../format";
import { realtime } from "../realtime";
import { useSession } from "../session";
import { useWorkspaces } from "../workspaces";
import type { ChatMessage, ChatPage, Workspace } from "../types";
import { Button, Checkbox, Dialog, EmptyState, Select, TextArea } from "../ui";
import "../components/chat.css";

function parseQuote(body: string, messages: ChatMessage[], parentId: string | null) {
  if (body.startsWith("> ")) {
    const parts = body.split("\n\n");
    const quoteLine = (parts[0] ?? "").slice(2).trim();
    const colonIdx = quoteLine.indexOf(":");
    let author = "Quote";
    let text = quoteLine;
    if (colonIdx > 0 && colonIdx < 40) {
      author = quoteLine
        .slice(0, colonIdx)
        .replace(/^\[|\]$/g, "")
        .trim();
      text = quoteLine.slice(colonIdx + 1).trim();
    }
    const cleanBody = parts.slice(1).join("\n\n").trim();
    return { author, text, cleanBody: cleanBody || body };
  }
  if (parentId) {
    const parent = messages.find((m) => m.id === parentId);
    if (parent) {
      return {
        author: parent.author?.display_name ?? "User",
        text: parent.body.slice(0, 100),
        cleanBody: body,
      };
    }
  }
  return null;
}

export function Chat({ ws }: { ws: Workspace }) {
  const { session } = useSession();
  const currentUserId = session?.user.id;
  const currentUsername = session?.user.username;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [moreNew, setMoreNew] = useState(false);
  const [earlier, setEarlier] = useState(false);
  const historyMode = useRef(false);
  const resetLatest = useRef(false);
  const viewGeneration = useRef(0);

  const [error, setError] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [taskSource, setTaskSource] = useState<ChatMessage | null>(null);
  const [thread, setThread] = useState<string | null>(null);

  // WhatsApp interaction states
  const [replyingTo, setReplyingTo] = useState<ChatMessage | null>(null);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [reactions, setReactions] = useState<Record<string, string[]>>({});
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [infoNotice, setInfoNotice] = useState<string | null>(null);

  const safeCursor = useRef(0);
  const generation = useRef(0);
  const catching = useRef(false);
  const queued = useRef(false);
  const refreshTimer = useRef<number | undefined>(undefined);
  const listRef = useRef<HTMLOListElement>(null);
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
    const token = generation.current;
    const view = ++viewGeneration.current;
    const first = messages[0];
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

  function addReaction(msgId: string, emoji: string) {
    setReactions((prev) => {
      const existing = prev[msgId] ?? [];
      const next = existing.includes(emoji) ? existing.filter((e) => e !== emoji) : [...existing, emoji];
      return { ...prev, [msgId]: next };
    });
    setActiveMenuId(null);
  }

  const filteredMessages = searchQuery.trim()
    ? messages.filter((m) => m.body.toLowerCase().includes(searchQuery.toLowerCase().trim()))
    : messages;

  return (
    <>
      <section className="chat" aria-label={`Chat in ${ws.name}`}>
        {blocked ? (
          <p role="alert">This chat is no longer available.</p>
        ) : (
          <div className="chat__panel">
            {/* WhatsApp Header */}
            <div className="chat__header">
              <div className="chat__header-info">
                <div className="chat__header-avatar">{ws.name.slice(0, 2).toUpperCase()}</div>
                <div className="chat__header-details">
                  <span className="chat__header-title">{ws.name}</span>
                  <span className="chat__header-status">online</span>
                </div>
              </div>
              <div className="chat__header-actions">
                <button
                  type="button"
                  className="chat__header-btn"
                  title="Video call"
                  aria-label="Video call"
                  onClick={() => setInfoNotice("Intranet video conferencing is active for research staff.")}
                >
                  📹
                </button>
                <button
                  type="button"
                  className="chat__header-btn"
                  title="Voice call"
                  aria-label="Voice call"
                  onClick={() => setInfoNotice("Intranet voice call relay is available.")}
                >
                  📞
                </button>
                <button
                  type="button"
                  className="chat__header-btn"
                  title="Search messages"
                  aria-label="Search messages"
                  onClick={() => setSearchOpen((v) => !v)}
                >
                  🔍
                </button>
                <button
                  type="button"
                  className="chat__header-btn"
                  title="Refresh chat"
                  aria-label="Refresh chat"
                  onClick={latest}
                >
                  ⋮
                </button>
              </div>
            </div>

            {/* In-chat search filter */}
            {searchOpen && (
              <div className="chat__search-bar">
                <input
                  className="chat__search-input"
                  placeholder="Search in chat…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button
                  type="button"
                  className="chat__header-btn"
                  onClick={() => {
                    setSearchQuery("");
                    setSearchOpen(false);
                  }}
                  aria-label="Close search"
                >
                  ✕
                </button>
              </div>
            )}

            {infoNotice && (
              <div className="chat__notice">
                {infoNotice}{" "}
                <Button variant="quiet" size="sm" onClick={() => setInfoNotice(null)}>
                  Dismiss
                </Button>
              </div>
            )}

            {/* Toolbar for older / earlier messages */}
            {(hasMore || moreNew || earlier) && (
              <div className="chat__toolbar">
                {hasMore && (
                  <Button variant="quiet" size="sm" onClick={older}>
                    Load earlier messages
                  </Button>
                )}
                {moreNew && (
                  <Button variant="quiet" size="sm" onClick={earlier ? latest : catchUp}>
                    Load new messages
                  </Button>
                )}
                {earlier && (
                  <Button variant="quiet" size="sm" onClick={latest}>
                    Return to latest messages
                  </Button>
                )}
              </div>
            )}

            {filteredMessages.length === 0 && (
              <EmptyState title="No messages yet.">
                {ws.can_contribute ? "Write the first message below." : "Messages will appear here."}
              </EmptyState>
            )}

            {/* Messages list with WhatsApp doodle wallpaper */}
            <ol className="chat__list" ref={listRef} aria-live="polite" aria-label="Chat messages">
              {filteredMessages.map((message, idx) => {
                const prev = filteredMessages[idx - 1];
                const currentDateBadge = fmtDateBadgeIST(message.created_at);
                const prevDateBadge = prev ? fmtDateBadgeIST(prev.created_at) : null;
                const showDateBadge = !prev || currentDateBadge !== prevDateBadge;

                const isMe =
                  (message.author && message.author.id === currentUserId) ||
                  (message.author && message.author.username === currentUsername);

                const quote = parseQuote(message.body, messages, message.parent_id);
                const displayBody = quote ? quote.cleanBody : message.body;
                const messageReactions = reactions[message.id] ?? [];

                return (
                  <div key={message.id} className="chat-bubble-row-wrapper" style={{ display: "contents" }}>
                    {showDateBadge && (
                      <div className="chat__date-pill" role="separator">
                        {currentDateBadge}
                      </div>
                    )}
                    <li
                      className={`chat-bubble-row ${isMe ? "chat-bubble-row--outgoing" : "chat-bubble-row--incoming"}`}
                    >
                      <div
                        className={`chat-bubble ${isMe ? "chat-bubble--outgoing" : "chat-bubble--incoming"}`}
                        onMouseLeave={() => activeMenuId === message.id && setActiveMenuId(null)}
                      >
                        {/* Author name for incoming messages */}
                        {!isMe && message.author && (
                          <button
                            type="button"
                            className="chat-bubble__author"
                            onClick={() => ws.can_contribute && setReplyingTo(message)}
                            title="Click to reply"
                          >
                            {message.author.display_name}
                          </button>
                        )}

                        {message.parent_id && <span className="chat__meta">Thread reply</span>}

                        {/* Quoted reply box inside message */}
                        {quote && (
                          <div className="chat-bubble__quote">
                            <span className="chat-bubble__quote-author">{quote.author}</span>
                            <span className="chat-bubble__quote-text">{quote.text}</span>
                          </div>
                        )}

                        {/* Message body text */}
                        <p className="chat-bubble__text">{displayBody}</p>

                        {/* Attachments */}
                        {message.attachments && message.attachments.length > 0 && (
                          <ChatFiles files={message.attachments} />
                        )}

                        {/* Footer with IST Clock Time & WhatsApp Blue Checkmarks */}
                        <div className="chat-bubble__meta">
                          <span className="chat-bubble__time">{fmtClockTimeIST(message.created_at)}</span>
                          {isMe && <span className="chat-bubble__ticks">✓✓</span>}
                        </div>

                        {/* Reactions badge */}
                        {ws.can_contribute && messageReactions.length > 0 && (
                          <button
                            type="button"
                            className="chat-bubble__reactions"
                            onClick={() => addReaction(message.id, "👍")}
                            title="Reactions"
                          >
                            {messageReactions.join(" ")}
                          </button>
                        )}

                        {/* Hover dropdown button */}
                        {ws.can_contribute && (
                          <button
                            type="button"
                            className="chat-bubble__actions-btn"
                            aria-label="Message options"
                            onClick={() =>
                              setActiveMenuId((curr) => (curr === message.id ? null : message.id))
                            }
                          >
                            ⌄
                          </button>
                        )}

                        {/* Hover dropdown menu */}
                        {ws.can_contribute && activeMenuId === message.id && (
                          <div className="chat-bubble__actions-menu">
                            <button
                              type="button"
                              onClick={() => {
                                setReplyingTo(message);
                                setActiveMenuId(null);
                              }}
                            >
                              ↩️ Reply
                            </button>
                            <button type="button" onClick={() => addReaction(message.id, "👍")}>
                              👍 React 👍
                            </button>
                            <button type="button" onClick={() => addReaction(message.id, "❤️")}>
                              ❤️ React ❤️
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setThread(message.parent_id ?? message.id);
                                setActiveMenuId(null);
                              }}
                            >
                              🧵 Open thread
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSummary(
                                  `Chat summary from ${ws.name}:\n> ${message.author?.display_name}: ${message.body}`,
                                );
                                setActiveMenuId(null);
                              }}
                            >
                              📢 Share to noticeboard
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setTaskSource(message);
                                setActiveMenuId(null);
                              }}
                            >
                              📋 Create task
                            </button>
                          </div>
                        )}
                      </div>
                    </li>
                  </div>
                );
              })}
            </ol>

            {error && (
              <p role="alert" className="chat__error" style={{ padding: "8px 16px" }}>
                {error}
              </p>
            )}

            {/* WhatsApp Composer */}
            <ChatComposer
              ws={ws}
              replyingTo={replyingTo}
              onClearReply={() => setReplyingTo(null)}
              sent={(message) => merge([message])}
              denied={deny}
            />

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
      </section>
      {!blocked && thread && (
        <ChatThread key={thread} ws={ws} rootId={thread} close={() => setThread(null)} />
      )}
    </>
  );
}

function PublishSummary({ source, text, onClose }: { source: Workspace; text: string; onClose: () => void }) {
  const { workspaces } = useWorkspaces();
  const targets = workspaces.filter((w) => w.can_contribute);
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
