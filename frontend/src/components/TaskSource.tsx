import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { Link } from "react-router-dom";
import { Button } from "../ui";
import "./task.css";
import { api, errorMessage, errorStatus } from "../api";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";

type Source = { workspace_id: string; workspace_name: string } & (
  | { kind: "post" | "chat"; id: string; body: string }
  | { kind: "board"; epoch: number; revision: number; current_epoch: number; current_revision: number }
);
const UNAVAILABLE = "Source unavailable or no longer accessible.";
const DENIAL_EVENTS = ["revoked", "subscribe_failed", "session_ended"];

function sourceNoun(source: Source): string {
  if (source.kind === "board") return "whiteboard";
  return source.kind === "post" ? "post" : "chat message";
}

function sourceRoute(source: Source): string {
  if (source.kind === "board") return "board";
  return source.kind === "post" ? "noticeboard" : "chat";
}

function SourceDetails({ source, close }: { source: Source; close: () => void }) {
  return (
    <>
      <p>
        Source {sourceNoun(source)} in {source.workspace_name}
      </p>
      {source.kind === "board" ? (
        <>
          <p>
            Recorded context: epoch {source.epoch}, revision {source.revision}.
          </p>
          <p>
            Current board: epoch {source.current_epoch}, revision {source.current_revision}. This opens the
            live board, not a saved image of the recorded context.
          </p>
        </>
      ) : (
        <p className="task__text">{source.body}</p>
      )}
      <Link to={`/w/${source.workspace_id}/${sourceRoute(source)}`}>
        Open source {source.kind === "board" ? "board" : "workspace"}
      </Link>
      <Button size="sm" onClick={close}>
        Close source reference
      </Button>
    </>
  );
}

export function TaskSource({ listId, taskId }: { listId: string; taskId: string }) {
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const { workspaces } = useWorkspaces();
  const visibility = workspaces
    .map((workspace) => workspace.id)
    .sort()
    .join("|");

  useEffect(() => {
    generation.current += 1;
    setSource(null);
    setLoading(false);
    // Before the first response we do not know the source workspace. Guard all
    // current readable scopes, including while a successful response is in flight.
    let active = true;
    const watchedIds = visibility ? visibility.split("|") : [];
    const stops = watchedIds.map((id) =>
      realtime.subscribe(id, (event) => {
        if (active && DENIAL_EVENTS.includes(event.type)) {
          generation.current += 1;
          setSource(null);
          setLoading(false);
          setError(UNAVAILABLE);
        }
      }),
    );
    return () => {
      active = false;
      invalidate(generation);
      stops.forEach((stop) => stop());
    };
  }, [visibility, listId, taskId]);

  async function load() {
    generation.current += 1;
    const token = generation.current;
    setLoading(true);
    setSource(null);
    setError("");
    try {
      const result = await api<Source>(`/todos/lists/${listId}/tasks/${taskId}/source`);
      if (token === generation.current) setSource(result);
    } catch (e: unknown) {
      if (token === generation.current) {
        const hidden = [403, 404].includes(errorStatus(e) ?? 0);
        setError(hidden ? UNAVAILABLE : errorMessage(e));
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }

  function close() {
    generation.current += 1;
    setSource(null);
  }

  return (
    <section className="task-panel" aria-label="Task source reference">
      <Button size="sm" disabled={loading} onClick={load}>
        {loading ? "Loading source…" : "View source reference"}
      </Button>
      {error && <p role="alert">{error}</p>}
      {source && <SourceDetails source={source} close={close} />}
    </section>
  );
}
