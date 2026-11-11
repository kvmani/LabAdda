import { useEffect, useRef, useState } from "react";
import { accessDenied, api, errorMessage } from "../api";
import { realtime } from "../realtime";
import { ChatFiles } from "./ChatFiles";
import { ChatComposer } from "./ChatComposer";
import { fmtTime } from "../format";
import type { ChatMessage, Workspace } from "../types";
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
    load();
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
      ++generation.current;
      stop();
    };
  }, [ws.id, rootId]);
  return (
    <section className="card chat-thread" aria-label="Chat thread" ref={section}>
      <h2>Thread discussion</h2>
      <button type="button" onClick={close}>
        Close thread
      </button>
      {blocked ? (
        <p role="alert">This thread is no longer available.</p>
      ) : (
        <>
          <button type="button" disabled={loading} onClick={() => load()}>
            Refresh thread
          </button>
          {changed && (
            <p role="status">Discussion may have changed. Refresh the thread; your reply draft is kept.</p>
          )}
          {loading && <p role="status">Loading thread…</p>}
          {error && <p role="alert">{error}</p>}
          {page && (
            <>
              <p className="preserve">
                <strong>{page.root.author?.display_name}</strong>: {page.root.body}
              </p>
              <ChatFiles files={page.root.attachments} />
              {page.messages.length === 0 ? (
                <p>No replies yet.</p>
              ) : (
                <ol>
                  {page.messages.map((message) => (
                    <li key={message.id}>
                      <strong>{message.author?.display_name}</strong> · {fmtTime(message.created_at)}
                      <p className="preserve">{message.body}</p>
                      <ChatFiles files={message.attachments} />
                    </li>
                  ))}
                </ol>
              )}
              {page.next_before && (
                <button type="button" disabled={loading} onClick={() => load(page.next_before!)}>
                  Older thread replies
                </button>
              )}
            </>
          )}
          <ChatComposer ws={ws} parentId={rootId} sent={() => load()} denied={deny} />
        </>
      )}
    </section>
  );
}
