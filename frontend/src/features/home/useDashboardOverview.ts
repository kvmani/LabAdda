import { useCallback, useEffect, useRef, useState } from "react";
import { invalidate } from "../../generation";
import { api, errorMessage } from "../../api";
import { missedEventGate, realtime } from "../../realtime";
import { useWorkspaces } from "../../workspaces";

export type Work = {
  id: string;
  list_id: string;
  list_title: string;
  workspace_id: string | null;
  workspace_name: string | null;
  title: string;
  due_date: string | null;
  priority: string;
  status: string;
};

export type Update = {
  id: string;
  kind: string;
  title: string;
  read: boolean;
  workspace: { id: string; name: string } | null;
};

export type Overview = {
  today: string;
  timezone: string;
  tasks: Work[];
  tasks_more: boolean;
  notes: { id: string; title: string; due_at: string }[];
  notes_more: boolean;
  updates: Update[];
  chats: { workspace_id: string; workspace_name: string; unread: number }[];
  chats_more: boolean;
  restart_required: boolean;
  observed_at: string;
};

const REFRESH_HINTS = ["tasks.changed", "chat.message", "noticeboard.changed", "access_changed"];
const DENIAL_EVENTS = ["revoked", "subscribe_failed", "session_ended"];

/** Loads member overview; realtime hints refresh stale items; lost grants drop data immediately. */
export function useDashboardOverview() {
  const { workspaces } = useWorkspaces();
  const visibility = workspaces
    .map((row) => row.id)
    .sort()
    .join("|");
  const [accessVersion, setAccessVersion] = useState(0);
  const scope = `${visibility}:${accessVersion}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const [record, setData] = useState<{ scope: string; value: Overview } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [changed, setChanged] = useState(false);
  const generation = useRef(0);
  const signals = useRef(0);

  const load = useCallback(async () => {
    generation.current += 1;
    const token = generation.current;
    const requestedScope = currentScope.current;
    const seenSignals = signals.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Overview>("/dashboard");
      if (token === generation.current && requestedScope === currentScope.current) {
        setData({ scope: requestedScope, value: result });
        if (seenSignals === signals.current) setChanged(false);
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e) + " The overview is unavailable; refresh to try again.");
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    setData(null);
    void load();
    let active = true;
    const watchedIds = visibility ? visibility.split("|") : [];
    const reconnected = missedEventGate();
    const stops = watchedIds.map((id) =>
      realtime.subscribe(id, (event) => {
        if (!active) return;
        if (DENIAL_EVENTS.includes(event.type) || event.type === "access_changed") {
          setAccessVersion((value) => value + 1);
          invalidate(generation);
          signals.current += 1;
          setData(null);
          setChanged(true);
        } else if (REFRESH_HINTS.includes(event.type) || reconnected(event)) {
          signals.current += 1;
          setChanged(true);
          void load();
        }
      }),
    );
    return () => {
      active = false;
      invalidate(generation);
      stops.forEach((stop) => stop());
    };
  }, [visibility, accessVersion, load]);

  const data = record?.scope === scope ? record.value : null;
  return { data, error, setError, loading, changed, load, generation, accessVersion };
}
