import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { fmtTime } from "../format";
import { realtime } from "../realtime";
import type { Post, SearchResults, Workspace } from "../types";
import { PostCard } from "../components/PostCard";
import { PostComposer } from "../components/PostComposer";
import { Button, Card, EmptyState, ErrorState, SearchInput, Skeleton } from "../ui";
import "./noticeboard.css";

type Feed = { pinned: Post[]; posts: Post[]; next_before: number | null };
type Upcoming = { id: string; title: string; due_at: string; kind?: string };

export function Noticeboard({ ws }: { ws: Workspace }) {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upcoming, setUpcoming] = useState<Upcoming[]>([]);
  const [results, setResults] = useState<SearchResults | null>(null);

  const load = useCallback(async () => {
    try {
      const [f, u] = await Promise.all([
        api<Feed>(`/workspaces/${ws.id}/posts`),
        api<{ items: Upcoming[] }>(`/workspaces/${ws.id}/upcoming`),
      ]);
      setFeed(f);
      setUpcoming(u.items);
      setError(null);
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }, [ws.id]);

  useEffect(() => {
    void load();
    return realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "noticeboard.changed" || ev.type === "subscribed") void load();
    });
  }, [load, ws.id]);

  async function more() {
    if (!feed?.next_before) return;
    const next = await api<Feed>(`/workspaces/${ws.id}/posts`, { params: { before: feed.next_before } });
    setFeed({ ...feed, posts: [...feed.posts, ...next.posts], next_before: next.next_before });
  }

  async function search(query: string) {
    if (query.length < 2) return setResults(null);
    try {
      setResults(await api<SearchResults>(`/workspaces/${ws.id}/search`, { params: { q: query } }));
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }

  const empty = feed !== null && feed.pinned.length + feed.posts.length === 0;
  return (
    <div className="notice-layout">
      <section className="feed" aria-label="Noticeboard feed">
        <PostComposer ws={ws} onPosted={load} />
        {error && <ErrorState message={error} onRetry={() => void load()} retryLabel="Retry" />}
        {!feed && !error && <Skeleton lines={4} label="Loading posts…" />}
        {empty && (
          <EmptyState title={`No posts yet in ${ws.name}.`}>
            {ws.can_write ? "Start the conversation above." : "Posts will appear here."}
          </EmptyState>
        )}
        {feed && !empty && (
          <>
            {feed.pinned.map((p) => (
              <PostCard key={p.id} post={p} ws={ws} onChanged={load} />
            ))}
            {feed.posts.map((p) => (
              <PostCard key={p.id} post={p} ws={ws} onChanged={load} />
            ))}
            {feed.next_before && <Button onClick={more}>Load older posts</Button>}
          </>
        )}
      </section>
      <aside className="secondary" aria-label="Upcoming and search">
        <Card title="Upcoming">
          {upcoming.length === 0 ? (
            <p className="notice-layout__muted">Nothing scheduled.</p>
          ) : (
            <ul className="notice-layout__list">
              {upcoming.map((u) => (
                <li key={u.id}>
                  <strong>{fmtTime(u.due_at)}</strong>
                  <br />
                  {u.title}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={`Search ${ws.name}`}>
          <SearchInput
            label="Search this workspace"
            placeholder="Posts and chat"
            onSearch={(q) => void search(q)}
            resultCount={results ? results.counts.posts + results.counts.chat : null}
          />
          {results && (
            <div className="notice-layout__results">
              <p className="notice-layout__muted">
                {results.counts.posts} posts · {results.counts.chat} chat messages
              </p>
              <ul className="notice-layout__list">
                {results.posts.map((p) => (
                  <li key={p.id}>📝 {p.body}</li>
                ))}
                {results.chat.map((c) => (
                  <li key={c.id}>
                    💬 {c.author?.display_name}: {c.body}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
        <Card title="Whiteboard">
          <Link to={`/w/${ws.id}/board`}>Open the live board</Link>
        </Card>
      </aside>
    </div>
  );
}
