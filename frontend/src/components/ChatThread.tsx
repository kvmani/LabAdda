import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { accessDenied, api, errorMessage } from "../api";
import { realtime } from "../realtime";
import { ChatFiles } from "./ChatFiles";
import { ChatComposer } from "./ChatComposer";
import { fmtTime } from "../format";
import type { ChatMessage, Workspace } from "../types";
import { Button, Card, Skeleton } from "../ui";
import "./chat.css";
type Page = { root: ChatMessage; messages: ChatMessage[]; next_before: number | null };
export function ChatThread({ ws, rootId, close }: { ws: Workspace; rootId: string; close: () => void }) {
  const [page, setPage] = useState<Page | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [changed, setChanged] = useState(false),
    [blocked, setBlocked] = useState(false);
  const generation = useRef(0),
    hints = useRef(0),
    section = useRef<HTMLElement>(null);
  function deny() {
    ++generation.current;
    setBlocked(true);
    setPage(null);
    setLoading(false);
  }
  async function load(before?: number) {
    const token = ++generation.current,
      seen = hints.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Page>(`/workspaces/${ws.id}/chat/${rootId}/replies`, { params: { before } });
      if (token === generation.current) {
        setPage(result);
        if (before === undefined && seen === hints.current) setChanged(false);
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
    const stop = realtime.subscribe(ws.id, (event) => {
      if (!active) return;
      if (
        event.type === "subscribed" ||
        (event.type === "chat.message" && event.message.parent_id === rootId)
      ) {
        ++hints.current;
        setChanged(true);
      }
      if (["revoked", "subscribe_failed", "session_ended"].includes(event.type)) deny();
    });
    return () => {
      active = false;
      invalidate(generation);
      stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload and resubscribe only when the thread changes
  }, [ws.id, rootId]);
  return (
    <section className="chat-thread" aria-label="Chat thread" ref={section}>
      <Card title="Thread discussion" actions={<Button onClick={close}>Close thread</Button>}>
        <div className="chat-thread__body">
          {blocked ? (
            <p role="alert">This thread is no longer available.</p>
          ) : (
            <>
              <div>
                <Button disabled={loading} onClick={() => load()}>
                  Refresh thread
                </Button>
              </div>
              {changed && (
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
                  {page.messages.length === 0 ? (
                    <p>No replies yet.</p>
                  ) : (
                    <ol className="chat__list">
                      {page.messages.map((message) => (
                        <li key={message.id}>
                          <strong>{message.author?.display_name}</strong> · {fmtTime(message.created_at)}
                          <p className="chat__text">{message.body}</p>
                          <ChatFiles files={message.attachments} />
                        </li>
                      ))}
                    </ol>
                  )}
                  {page.next_before && (
                    <div>
                      <Button disabled={loading} onClick={() => load(page.next_before!)}>
                        Older thread replies
                      </Button>
                    </div>
                  )}
                </>
              )}
              <ChatComposer ws={ws} parentId={rootId} sent={() => load()} denied={deny} />
            </>
          )}
        </div>
      </Card>
    </section>
  );
}
