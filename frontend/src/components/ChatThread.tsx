import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { accessDenied, api, errorMessage } from "../api";
import { missedEventGate, realtime } from "../realtime";
import { ChatFiles } from "./ChatFiles";
import { ChatComposer } from "./ChatComposer";
import { fmtTime } from "../format";
import type { ChatMessage, Workspace } from "../types";
import { Button, Card, Skeleton } from "../ui";
import "./chat.css";
type Page = { root: ChatMessage; messages: ChatMessage[]; next_before: number | null };

const DENIAL_EVENTS = ["revoked", "subscribe_failed", "session_ended"];

/** Thread replies plus a content-free "may have changed" hint; late responses are discarded. */
function useThreadReplies(ws: Workspace, rootId: string) {
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [changed, setChanged] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const generation = useRef(0);
  const hints = useRef(0);
  const section = useRef<HTMLElement>(null);

  function deny() {
    generation.current += 1;
    setBlocked(true);
    setPage(null);
    setLoading(false);
  }

  async function load(before?: number) {
    generation.current += 1;
    const token = generation.current;
    const seenHints = hints.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Page>(`/workspaces/${ws.id}/chat/${rootId}/replies`, { params: { before } });
      if (token === generation.current) {
        setPage(result);
        if (before === undefined && seenHints === hints.current) setChanged(false);
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (accessDenied(e)) deny();
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    void load();
    section.current?.scrollIntoView({ block: "start" });
    const reconnected = missedEventGate();
    const stop = realtime.subscribe(ws.id, (event) => {
      if (!active) return;
      const isThreadReply = event.type === "chat.message" && event.message.parent_id === rootId;
      if (reconnected(event) || isThreadReply) {
        hints.current += 1;
        setChanged(true);
      }
      if (DENIAL_EVENTS.includes(event.type)) deny();
    });
    return () => {
      active = false;
      invalidate(generation);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload and resubscribe only when the thread changes
  }, [ws.id, rootId]);

  return { page, error, loading, changed, blocked, section, load, deny };
}

function ReplyList({ messages }: { messages: ChatMessage[] }) {
  if (messages.length === 0) return <p>No replies yet.</p>;
  return (
    <ol className="chat__list">
      {messages.map((message) => (
        <li key={message.id}>
          <strong>{message.author?.display_name}</strong> · {fmtTime(message.created_at)}
          <p className="chat__text">{message.body}</p>
          <ChatFiles files={message.attachments} />
        </li>
      ))}
    </ol>
  );
}

export function ChatThread({ ws, rootId, close }: { ws: Workspace; rootId: string; close: () => void }) {
  const thread = useThreadReplies(ws, rootId);
  const { page, loading, error } = thread;
  return (
    <section className="chat-thread" aria-label="Chat thread" ref={thread.section}>
      <Card title="Thread discussion" actions={<Button onClick={close}>Close thread</Button>}>
        <div className="chat-thread__body">
          {thread.blocked ? (
            <p role="alert">This thread is no longer available.</p>
          ) : (
            <>
              <div>
                <Button disabled={loading} onClick={() => thread.load()}>
                  Refresh thread
                </Button>
              </div>
              {thread.changed && (
                <p role="status">
                  Discussion may have changed. Refresh the thread; your reply draft is kept.
                </p>
              )}
              {loading && !page && <Skeleton lines={3} label="Loading thread…" />}
              {loading && page && <p role="status">Loading thread…</p>}
              {error && (
                <p className="chat__error" role="alert">
                  {error}
                </p>
              )}
              {page && (
                <>
                  <p className="chat__text">
                    <strong>{page.root.author?.display_name}</strong>: {page.root.body}
                  </p>
                  <ChatFiles files={page.root.attachments} />
                  <ReplyList messages={page.messages} />
                  {page.next_before && (
                    <div>
                      <Button disabled={loading} onClick={() => thread.load(page.next_before!)}>
                        Older thread replies
                      </Button>
                    </div>
                  )}
                </>
              )}
              <ChatComposer ws={ws} parentId={rootId} sent={() => thread.load()} denied={thread.deny} />
            </>
          )}
        </div>
      </Card>
    </section>
  );
}
